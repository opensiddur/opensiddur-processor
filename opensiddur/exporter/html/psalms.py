"""Present liturgical psalms consistently in the expanded electronic siddur."""
import re
import unicodedata
from lxml import etree
from opensiddur.exporter.constants import TEI_NS, PROCESSING_NAMESPACE, JLPTEI_NAMESPACE

T='{'+TEI_NS+'}'; P='{'+PROCESSING_NAMESPACE+'}'; J='{'+JLPTEI_NAMESPACE+'}'
LANG='{http://www.w3.org/XML/1998/namespace}lang'
FULL=re.compile(r'urn:x-opensiddur:text:bible:psalms/([1-9]\d{0,2})$')
ALIASES={
    'urn:x-opensiddur:text:prayer:mizmor_shir_chanukat_habayit':30,
    'urn:x-opensiddur:text:siddur:chol/shacharit/pesuqei_dezimrah/psalm_150':150,
}


def hebrew_number(number):
    if not 1 <= number <= 150:
        raise ValueError('Psalm number must be between 1 and 150')
    prefix='ק' if number >= 100 else ''; number%=100
    if number in (15,16):return prefix+{15:'טו',16:'טז'}[number]
    return prefix+('יכלמנסעפצ'[number//10-1] if number>=10 else '')+('אבגדהוזחט'[number%10-1] if number%10 else '')


def psalm_number(urn):
    match=FULL.fullmatch(urn or '')
    if match and 1 <= int(match[1]) <= 150:return int(match[1])
    return ALIASES.get(urn)


def title(number, language):
    return 'תהלים '+hebrew_number(number) if language=='he' else 'Psalm '+str(number)


def heading_number(heading):
    text=' '.join(''.join(heading.itertext()).split())
    text=''.join(c for c in unicodedata.normalize('NFD',text) if not unicodedata.category(c).startswith('M'))
    match=re.fullmatch(r'Psalm\s+(\d+)',text,re.I)
    if match:
        number=int(match[1]); return ('en',number) if 1<=number<=150 else None
    match=re.fullmatch(r'תהלים\s+([א-ת\d׳״\'\"]+)',text)
    if not match:return None
    digits=match[1].replace('׳','').replace('״','').replace("'",'').replace('"','')
    if digits.isdigit():number=int(digits)
    else:
        values=dict(zip('אבגדהוזחטיכלמנסעפצק',[1,2,3,4,5,6,7,8,9,10,20,30,40,50,60,70,80,90,100]))
        number=sum(values.get(c,1000) for c in digits)
        if 1<=number<=150 and digits!=hebrew_number(number):return None
    return ('he',number) if 1<=number<=150 else None


def normalize(root):
    """Add one bilingual title per whole psalm, retaining passages and scope markers.

    Only a book whose settings ask for `electronic.psalm_titles: uniform` is normalized;
    others retain their printed titles. Verse-range references and composite prayers such as Ashrei keep their own
    titles. Wrapper headings inherit the transclusion's conditional position.
    """
    report={'wrapped':0,'normalized':0,'redundant':0,'chapter_labels':0}
    for reference in list(root.iter(P+'transclude')):
        number=psalm_number(reference.get('target'))
        if number is None or reference.get('targetEnd') or any(a.tag==T+'note' for a in reference.iterancestors()):continue
        if any(a.tag==T+'div' and a.get('type')=='psalm' and a.get('n')==str(number) for a in reference.iterancestors()):continue
        wrapper=etree.Element(T+'div',type='psalm',n=str(number))
        for language in ('he','en'):
            heading=etree.SubElement(wrapper,T+'head');heading.set(LANG,language);heading.text=title(number,language)
        wrapper.tail=reference.tail;reference.tail=None
        reference.getparent().replace(reference,wrapper);wrapper.append(reference);report['wrapped']+=1
    pending={}
    walker=etree.iterwalk(root,events=('start',))
    for _,node in walker:
        if node.tag==T+'note':walker.skip_subtree();continue
        if node.tag==T+'head':
            walker.skip_subtree()
            # These edition titles are suppressed by the psalm wrapper's XSLT.
            if node.getparent().get('type')!='psalm' and any(a.tag==T+'div' and a.get('type')=='psalm' for a in node.iterancestors()):continue
            key=heading_number(node)
            if key is None:pending.clear();continue
            language,number=key
            node.set(LANG,language);node.set(P+'psalm-title',title(number,language))
            report['normalized']+=1
            if key in pending:
                previous=pending[key]
                if node.getparent().get('type')=='psalm':previous.set(P+'suppress-psalm-heading','true')
                else:node.set(P+'suppress-psalm-heading','true');report['redundant']+=1;continue
                report['redundant']+=1
            pending[key]=node
        elif node.tag in (T+'p',T+'l',T+'ab',J+'conditional',J+'endConditional'):
            pending.clear()
        elif node.tag==T+'milestone' and node.get('unit')=='chapter' and psalm_number(node.get('corresp')) is not None:
            node.set(P+'chapter-label','hidden');report['chapter_labels']+=1
    return report
