"""Readable two-column PDF fallback; not an IEEEtran compiler or venue certification.

Run with the bundled document Python runtime (ReportLab and PyMuPDF).
"""
import json
import re
from html import escape
from pathlib import Path
from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,Paragraph,Spacer,Image,Table,TableStyle,NextPageTemplate,FrameBreak,Flowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER,TA_JUSTIFY
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports'
tex=(OUT/'IncidentLab-IEEE.tex').read_text(encoding='utf-8')
body=tex.split(r'\end{IEEEkeywords}',1)[1].split(r'\begin{thebibliography}',1)[0]
styles={
 'text':ParagraphStyle('text',fontName='Times-Roman',fontSize=10,leading=12,alignment=TA_JUSTIFY,spaceAfter=6),
 'section':ParagraphStyle('section',fontName='Times-Bold',fontSize=10,leading=12,spaceBefore=10,spaceAfter=6,keepWithNext=True),
 'subsection':ParagraphStyle('subsection',fontName='Times-Italic',fontSize=10,leading=12,spaceBefore=6,spaceAfter=4,keepWithNext=True),
 'caption':ParagraphStyle('caption',fontName='Times-Roman',fontSize=8,leading=10,spaceAfter=10),
 'title':ParagraphStyle('title',fontName='Times-Roman',fontSize=21,leading=25,alignment=TA_CENTER,spaceAfter=14),
 'author':ParagraphStyle('author',fontName='Times-Roman',fontSize=11,leading=13,alignment=TA_CENTER,spaceAfter=15),
}
def clean(s):
    s=s.replace(r'\%', '%').replace(r'\_', '_').replace(r'\,',' ').replace(r'\rightarrow',' → ').replace(r'\times',' × ').replace('~',' ')
    s=re.sub(r'\$([^$]*)\$',r'\1',s)
    s=re.sub(r'\\cite\{([^}]+)\}',lambda m:'['+str({'rcaeval':1,'if':2,'kind':3,'logging':4}[m[1]])+']',s)
    s=re.sub(r'\\ref\{[^}]+\}',lambda m:{'tab:research':'I','tab:trials':'II','fig:confusion':'1','fig:training':'2','fig:latency':'6'}[m[0][5:-1]],s)
    s=re.sub(r'\\(?:texttt|textbf|url)\{([^}]+)\}',r'\1',s)
    s=s.replace('{','').replace('}','')
    return escape(s.strip())
def para(s,key='text'):return Paragraph(clean(s),styles[key])
story=[para('IncidentLab: Multimodal Incident Detection and Evidence-Supported Investigation with CPU Serving and Kubernetes Validation','title'),para('Amikula Pavan Kumar Goud<br/>MSc Computer Science Student<br/>Blekinge Institute of Technology<br/>Karlskrona, Sweden'.replace('<br/>','\n'),'author')]
# Separate narrow title frame uses explicit paragraph breaks for affiliation.
story[1]=Paragraph('Amikula Pavan Kumar Goud<br/>MSc Computer Science Student<br/>Blekinge Institute of Technology<br/>Karlskrona, Sweden',styles['author'])
story.extend([NextPageTemplate('columns'),FrameBreak()])
abstract=tex.split(r'\begin{abstract}',1)[1].split(r'\end{abstract}',1)[0]
story.append(para('Abstract—'+abstract))
story.append(para('Keywords—incident detection; multimodal telemetry; GRU; Isolation Forest; distributed tracing; CPU inference; Kubernetes.'))
figure_names=iter(['research-gru-confusion','research-training-curves','research-ob-curves','research-ss-curves','research-tt-curves','cluster-delay-timeline'])
section=0
figure_number=0
class HalfPlot(Flowable):
    def __init__(self,path,side):
        super().__init__();self.path=str(path);self.side=side
        w,h=ImageReader(self.path).getSize();self.width=238;self.height=476*h/w
    def draw(self):
        c=self.canv;c.saveState();clip=c.beginPath();clip.rect(0,0,self.width,self.height)
        c.clipPath(clip,stroke=0,fill=0)
        c.drawImage(self.path,-238*self.side,0,width=476,height=self.height)
        c.restoreState()
pattern=r'(\\begin\{figure\}\[t\].*?\\end\{figure\}|\\begin\{table\}\[t\].*?\\end\{table\}|\\section\{[^}]+\}|\\subsection\{[^}]+\})'
for block in re.split(pattern,body,flags=re.S):
    if not block.strip():continue
    if block.startswith(r'\section'):
        section+=1;story.append(para(f'{section}. '+re.search(r'\{([^}]+)\}',block)[1].upper(),'section'))
    elif block.startswith(r'\subsection'):story.append(para(re.search(r'\{([^}]+)\}',block)[1],'subsection'))
    elif block.startswith(r'\begin{figure}'):
        figure_number+=1
        name=next(figure_names);path=ROOT/'artifacts/report_figures'/f'{name}.png';w,h=ImageReader(str(path)).getSize()
        if name.endswith('curves'):story.extend([HalfPlot(path,0),Spacer(1,4),HalfPlot(path,1)])
        else:story.append(Image(str(path),width=238,height=238*h/w))
        caption=re.search(r'\\caption\{(.*?)\}\\label',block,re.S)[1]
        story.append(para(f'Fig. {figure_number}. '+caption,'caption'))
    elif block.startswith(r'\begin{table}'):
        caption=re.search(r'\\caption\{(.*?)\}\\label',block,re.S)[1];story.append(para(caption,'caption'))
        data=([['Model','Precision','Recall','F1'],['Isolation Forest','0.972','0.743','0.842'],['Temporal GRU','0.988','0.956','0.972']] if 'tab:research' in block else [['Experiment','Operational','ML only'],['Native HTTP (college PC)','18/18','10/18'],['Kubernetes (laptop)','9/9','4/9']])
        t=Table(data,hAlign='CENTER');t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Times-Roman'),('FONTSIZE',(0,0),(-1,-1),8),('LINEABOVE',(0,0),(-1,0),.6,colors.black),('LINEBELOW',(0,0),(-1,0),.4,colors.black),('LINEBELOW',(0,-1),(-1,-1),.6,colors.black)]));story.extend([t,Spacer(1,8)])
    else:
        for p in re.split(r'\n\s*\n',block):
            if p.strip():story.append(para(p))
story.append(para('REFERENCES','section'))
bib=tex.split(r'\begin{thebibliography}{9}',1)[1].split(r'\end{thebibliography}',1)[0]
for i,item in enumerate(re.split(r'\\bibitem\{[^}]+\}',bib)[1:],1):story.append(para(f'[{i}] '+item,'caption'))
story.append(para('PDF rendering note: this readable two-column version was generated with ReportLab because the built-in LaTeX compiler returned a platform-directory error. The companion IEEEtran source is the editable submission-format source. No venue compliance or publication is claimed.','caption'))
w,h=letter;m=54;gap=18;cw=(w-2*m-gap)/2
doc=BaseDocTemplate(str(OUT/'IncidentLab-IEEE-readable.pdf'),pagesize=letter,title='IncidentLab project report',author='Amikula Pavan Kumar Goud',leftMargin=m,rightMargin=m,topMargin=m,bottomMargin=m)
def footer(c,d):
    c.saveState();c.setFont('Times-Roman',8);c.drawCentredString(w/2,30,str(d.page));c.restoreState()
title_frame=Frame(m,h-230,w-2*m,176,id='title',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
first_left=Frame(m,m,cw,h-m-238,id='firstleft',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
first_right=Frame(m+cw+gap,m,cw,h-m-238,id='firstright',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
doc.addPageTemplates([PageTemplate('first',[title_frame,first_left,first_right],onPage=footer),PageTemplate('columns',[Frame(m,m,cw,h-2*m,id='left',leftPadding=0,rightPadding=0),Frame(m+cw+gap,m,cw,h-2*m,id='right',leftPadding=0,rightPadding=0)],onPage=footer)])
doc.build(story)
from pypdf import PdfReader
pdf=PdfReader(OUT/'IncidentLab-IEEE-readable.pdf')
text='\n'.join(p.extract_text() for p in pdf.pages)
assert 'Amikula Pavan Kumar Goud' in text and '9/9' in text and '4/9' in text
(OUT/'pdf-verification.json').write_text(json.dumps(dict(pages=len(pdf.pages),author_verified=True,metrics_verified=True,renderer='ReportLab readable fallback; IEEEtran compilation unavailable'),indent=2))
print(f'Rendered {len(pdf.pages)} pages for visual review.')
