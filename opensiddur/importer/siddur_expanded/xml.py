"""Small XML authoring helpers, independent of source data."""
from html import escape
from itertools import count

from lxml import etree as E

from opensiddur.importer.birnbaum_scan.build.common import (
    PROJECT_HE as BIRNBAUM_PROJECT,
)
from opensiddur.importer.humash.build import PROJECT as HUMASH_PROJECT

T = 'http://www.tei-c.org/ns/1.0'
J = 'http://jewishliturgy.org/ns/jlptei/2'
NS = {'tei': T, 'j': J}
XID = '{http://www.w3.org/XML/1998/namespace}id'
ROOT = 'urn:x-opensiddur:text:siddur:expanded'
PROJECT = 'siddur_expanded-opensiddur-he'
TEXT = 'urn:x-opensiddur:text:'

def feature(group, name, value=True, maximum=None):
    if isinstance(value, bool): tag, value = 'binary', str(value).lower()
    elif isinstance(value, int): tag = 'numeric'
    else: tag = 'string'
    v = f'<tei:{tag} value="{escape(str(value), quote=True)}"'+(f' max="{maximum}"' if maximum else '')+'/>' if tag != 'string' else '<tei:string>'+escape(value)+'</tei:string>'
    return f'<tei:fs type="opensiddur:{group}"><tei:f name="{name}">{v}</tei:f></tei:fs>'

def all_of(*values):
    values=[v for v in values if v]
    return '<j:all>'+''.join(values)+'</j:all>' if values else ''
def any_of(*values): return '<j:any>'+''.join(values)+'</j:any>'
def none_of(*values): return '<j:none>'+''.join(values)+'</j:none>'
def holiday(name, first=1, last=None): return feature('holiday', name, first, last)
def aggregate(name): return feature('holiday-aggregate', name)
def service(name): return feature('service-time', name)
def transclude(urn): return f'<j:transclude type="external" target="{escape(urn, quote=True)}"/>'
def head(he, en): return f'<tei:head xml:lang="he">{escape(he)}</tei:head><tei:head xml:lang="en">{escape(en)}</tei:head>'
def instruction(text): return '<tei:note type="instruction" xml:lang="en">'+escape(text)+'</tei:note>'

class Author:
    def __init__(self): self.ids = count(1)
    def gate(self, predicate, body, rubric=''):
        ident = 'expanded_condition_'+str(next(self.ids))
        return f'<j:conditional xml:id="{ident}">'+(instruction(rubric) if rubric else '')+predicate+'</j:conditional>'+body+f'<j:endConditional target="#{ident}"/>'
    def context(self, body, service_name, repetition=False):
        ident = 'expanded_context_'+str(next(self.ids))
        values = ''.join(f'<tei:f name="{n}"><tei:binary value="{str(n==service_name).lower()}"/></tei:f>' for n in ['shaharit','minha','maariv','musaf','neila','slihot'])
        values = '<tei:fs type="opensiddur:service-time">'+values+'</tei:fs>'
        values += f'<tei:fs type="opensiddur:recitation"><tei:f name="silent"><tei:binary value="{str(not repetition).lower()}"/></tei:f><tei:f name="repetition"><tei:binary value="{str(repetition).lower()}"/></tei:f></tei:fs>'
        # Eligibility is tested by the caller before this context is entered.
        # Even when that eligibility is undecided, a reader's repetition is
        # intrinsically public; its internal rubrics must not remain undecided.
        if repetition:
            values += feature('quorum', 'minyan')
        return f'<j:declare xml:id="{ident}">'+values+'</j:declare>'+body+f'<j:endDeclare target="#{ident}"/>'

def document(name, he, en, body):
    urn = ROOT+('/'+name if name != 'index' else '')
    source = '<tei:bibl>This project arranges prayer text from Birnbaum 1949 and readings from the Humash and Tanakh editions. '
    source += f'See <tei:ref target="{ROOT}@{PROJECT}">the project index</tei:ref> for the editorial arrangement.</tei:bibl>'
    return f'''<tei:TEI xmlns:tei="{T}" xmlns:j="{J}" xml:lang="he">
<tei:teiHeader><tei:fileDesc><tei:titleStmt><tei:title type="main" xml:lang="he">{escape(he)}</tei:title><tei:title type="alt" xml:lang="en">{escape(en)}</tei:title>
<tei:respStmt><tei:resp key="mrk">Arrangement and markup</tei:resp><tei:name ref="urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein">Efraim Feinstein</tei:name></tei:respStmt></tei:titleStmt>
<tei:editionStmt><tei:p>Expanded Ashkenazi siddur: prayers in recitation order. Prayer words are transcluded from their source editions. Birnbaum supplies selected High Holiday services and rites, not a complete mahzor.</tei:p></tei:editionStmt>
<tei:publicationStmt><tei:distributor><tei:ref target="https://opensiddur.org">Open Siddur Project</tei:ref></tei:distributor><tei:idno type="urn">{urn}@{PROJECT}</tei:idno><tei:availability status="free"><tei:licence target="https://creativecommons.org/licenses/by-sa/4.0/">Creative Commons Attribution-ShareAlike 4.0</tei:licence></tei:availability></tei:publicationStmt>
<tei:sourceDesc>{source}<tei:bibl><tei:title>Birnbaum, ha-Siddur ha-Shalem (1949)</tei:title><tei:ptr target="urn:x-opensiddur:text:siddur:siddur@{BIRNBAUM_PROJECT}"/></tei:bibl><tei:bibl><tei:title>Humash reading divisions</tei:title><tei:ptr target="urn:x-opensiddur:text:bible:chumash@{HUMASH_PROJECT}"/></tei:bibl></tei:sourceDesc></tei:fileDesc></tei:teiHeader>
<tei:text><tei:body><tei:div corresp="{urn}">{head(he,en) if name in ['index','appendices'] else ''}{body}</tei:div></tei:body></tei:text></tei:TEI>'''

def parse_fragment(text): return E.fromstring(f'<root xmlns:tei="{T}" xmlns:j="{J}">{text}</root>'.encode())
def serialize(element):
    s = E.tostring(element, encoding='unicode', with_tail=False)
    return s.replace(f' xmlns:tei="{T}"','').replace(f' xmlns:j="{J}"','')
