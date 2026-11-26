"""All seven printed Hallel commentary notes, including the facing-page continuation."""
from .hallel import ROOT
from .hallel_data import PAGES
from .notes_motzaei_shabbat import xml

NOTES=[]
for page,key in [(565,''),(567,'/psalm_114'),(568,'/psalm_115'),(569,'/psalm_116'),(571,'/psalm_117'),(573,'/yehallelukha')]:
    for i,text in enumerate(PAGES[str(page)]['notes']):
        if page==565:text+=' '+PAGES['566']['notes'][0]
        target=ROOT+('/psalm_118' if page==571 and i==1 else key)
        NOTES.append(dict(target=target,kind='commentary',lemma='',n='',paras=[dict(text=xml(text))]))
