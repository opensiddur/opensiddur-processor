"""PDF measurement algorithms; callers supply edition geometry and fingerprints."""
import copy
import re
import unicodedata

from .pdf_direction import base


def glyph_rows(tree, minimum_font_size=None, *, gutters, heading=None, normalize=unicodedata.normalize):
    he,en,headings=[],[],[]
    for number,page in enumerate(tree.findall('page'),1):
        gutter=gutters[(number-1)%len(gutters)]
        hrows,erows={},{}
        for line in page.findall('.//line'):
            chars=line.findall('.//char') if minimum_font_size is None else [c for font in line.findall('font') if float(font.get('size','100'))>minimum_font_size for c in font.findall('char')]
            hebrew=''.join(base(c.get('c',' ')) or '' for c in sorted(chars,key=lambda c:float(c.get('x')),reverse=True))
            if hebrew==heading and not any(c.get('c','').isdigit() for c in chars):headings.append((number,min(float(c.get('y')) for c in chars)))
            for c in chars:
                x=float(c.get('x'));y=round(float(c.get('y')),2)
                if x<gutter and base(c.get('c',' ')):hrows.setdefault(y,[]).append(c)
                elif x>gutter:erows.setdefault(y,[]).append(c)
        he.extend((number,y,''.join(base(c.get('c')) for c in sorted(chars,key=lambda c:float(c.get('x')),reverse=True))) for y,chars in hrows.items())
        for y,chars in erows.items():
            words='';right=None
            for c in sorted(chars,key=lambda c:float(c.get('x'))):
                if right is not None and float(c.get('x'))-right>2 and words and not words[-1].isspace():words+=' '
                words+=c.get('c','');quad=list(map(float,c.get('quad').split()));right=max(quad[0::2])
            en.append((number,y,normalize('NFKC', words)))
    return he,en,headings


def body_text(tree, *, gutters, minimum_font_size, header_bottom, normalize=unicodedata.normalize):
    # Remove page/header counters before joining a word across a PDF page break.
    rows=glyph_rows(tree,minimum_font_size=minimum_font_size,gutters=gutters,normalize=normalize)[1]
    text=strip_numeric_markers(normalize('NFKC', ' '.join(text for _,y,text in rows if not(y<header_bottom and text.strip().isdigit()))))
    return normalize('NFKC', re.sub(r'(?<=\w)-\s+(?=\w)','',' '.join(text.split())))


def latin_note_runs(tree, *, maximum_font_size):
    """Group small Latin glyphs by font and baseline, including fragmented PDF lines."""
    runs = {}
    for page_no, page in enumerate(tree.findall('page'), 1):
        for font in page.findall('.//font'):
            if float(font.get('size', '100')) > maximum_font_size:
                continue
            for char in font.findall('char'):
                value = char.get('c', '')
                if value.isascii() and value.isalpha():
                    key = (page_no, round(float(char.get('y')), 2), font.get('name'))
                    runs.setdefault(key, []).append(char)
    return {key: chars for key, chars in runs.items() if len(chars) >= 4}


def outline_rows(reader):
    rows=[]
    def walk(items, depth):
        for item in items:
            if isinstance(item,list):walk(item,depth+1)
            else:rows.append((depth, str(item.title), reader.get_destination_page_number(item)+1,
                              float(item.top) if item.top is not None else None))
    walk(reader.outline,0)
    return rows


def day_bookmarks(rows, captions, *, child_caption):
    days=[]
    for caption in captions:
        hits=[r for r in rows if caption in r[1] and r[0]==0]
        if len(hits)!=1:raise ValueError('Each section requires one top-level bookmark: '+caption)
        days.append(hits[0])
    for day in days:
        index=rows.index(day)
        descendants=[]
        for row in rows[index+1:]:
            if row[0]<=day[0]:break
            descendants.append(row)
        if not any(row[0]>day[0] and child_caption in row[1] for row in descendants):
            raise ValueError('Section bookmark must contain its expected child heading')
    return days


def check_contents(tree, rows, page_labels, *, number_columns, caption):
    """Compare rendered TOC numbers with the current bookmark destinations."""
    numbers=[];in_contents=False
    first_body_page=min(row[2] for row in rows)
    for number,page in enumerate(tree.findall('page'),1):
        if any(caption in line.get('text','') for line in page.findall('.//line')):
            in_contents=True
        elif in_contents and number>=first_body_page:
            break
        if not in_contents:continue
        baselines={}
        for line in page.findall('.//line'):
            # The caller supplies the number-column cutoff for each mirrored page.
            number_column=number_columns[(number-1)%len(number_columns)]
            digits=[c for c in line.findall('.//char') if c.get('c','').isdigit() and float(c.get('x'))>=number_column]
            xs=[float(c.get('x')) for c in digits]
            if xs!=sorted(xs):raise ValueError('Reversed TOC page number')
            for char in digits:
                baseline=round(float(char.get('y')),2)
                baselines.setdefault(baseline,[]).append(char)
        numbers.extend(''.join(c.get('c') for c in sorted(chars,key=lambda c:float(c.get('x'))))
                       for _,chars in sorted(baselines.items()))
    expected=[page_labels[row[2]-1] for row in rows]
    if numbers!=expected:raise ValueError(f'TOC pages differ from bookmark destinations: {numbers} != {expected}')


def slice_day(tree, start, end=None, keep_titles=False, trailing_note_texts=(), prior_note_texts=(), *, title_pages, maximum_note_size, boundary_tolerance):
    """Retain original page slots, so parity-dependent column gutters remain valid."""
    result=copy.deepcopy(tree)
    pages=result.findall('page')
    start_page,start_top=start[2],start[3]
    end_page,end_top=(end[2],end[3]) if end else (len(pages)+1,None)
    for number,page in enumerate(pages,1):
        height=float(page.get('height'))
        for line in list(page.findall('.//line')):
            chars=line.findall('.//char')
            y=float(chars[0].get('y')) if chars else float('inf')
            after_start=number>start_page or (number==start_page and y>=height-start_top-boundary_tolerance)
            before_end=number<end_page or (number==end_page and y<height-end_top-boundary_tolerance)
            title=keep_titles and number<=title_pages
            # An earlier service's apparatus can sit below the next body heading.
            trailing_note=(number==end_page and any(phrase in line.get('text','') for phrase in trailing_note_texts)
                           and any(float(font.get('size','100'))<=maximum_note_size for font in line.findall('.//font')))
            prior_note=(number==start_page and any(phrase in line.get('text','') for phrase in prior_note_texts)
                        and any(float(font.get('size','100'))<=maximum_note_size for font in line.findall('.//font')))
            if prior_note or not(title or (after_start and before_end) or trailing_note):line.getparent().remove(line)
    return result


def strip_numeric_markers(text):
    """Normalize PDF body fingerprints, never the source or rendered text."""
    return re.sub(r'(?<=[A-Za-z,.;:!?])[\s\d]*\d(?=[,.;!?]|\s)','',text)
