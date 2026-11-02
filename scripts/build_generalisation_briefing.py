"""Build the editable 24-page Governed Agent Fabric collaborator briefing.

Uses ReportLab with Windows Calibri/Georgia fonts; no network access. Original
briefing/source remain untouched. All diagrams are vector shapes in this source.
Run: python scripts/build_generalisation_briefing.py
Optional --status-json supplies updated evidence/status strings without editing
page layouts. Outputs PDF plus layout/text QA manifests in .local/pdf-generalisation.
"""
from pathlib import Path
import argparse
import json
import math
from xml.sax.saxutils import escape

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT/'docs/Governed_Agent_Fabric_Generalisation.pdf')
parser.add_argument('--work', type=Path, default=ROOT/'.local/pdf-generalisation')
parser.add_argument('--status-json', type=Path)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
args.work.mkdir(parents=True, exist_ok=True)

STATUS = {
    'date': '2 November 2026',
    'designer': 'The final Qwen3:8b vendor draft passed mechanical checks on the first attempt; museum drafts failed validation. Assistant review found faulty paths, inferred authority and weak tests. Substantive human revision is required; earlier failures are retained.',
    'tests': 'The local regression passed 129 core tests (including 29 designer/CLI tests), 12 Rego tests, 77 enterprise contracts and 3 original AGT tests. These scopes do not establish production readiness.',
    'native': 'Real PostgreSQL 16.2 passed the two generic workflow journeys, concurrency and restart checks with synthetic targets. Full eighteen-component native acceptance remains incomplete.',
    'release': 'This document describes a development snapshot, not a production approval or compliance certification.',
}
if args.status_json:
    updates = json.loads(args.status_json.read_text(encoding='utf-8'))
    if not isinstance(updates, dict) or set(updates) - set(STATUS) or not all(isinstance(v, str) for v in updates.values()):
        raise ValueError('Status overrides must be known string fields')
    STATUS.update(updates)

FONTS = Path('C:/Windows/Fonts')
for family, filename in [('Body','calibri.ttf'),('Bold','calibrib.ttf'),('Italic','calibrii.ttf'),('Display','georgia.ttf'),('DisplayBold','georgiab.ttf')]:
    pdfmetrics.registerFont(TTFont(family, str(FONTS/filename)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold', italic='Italic', boldItalic='Bold')

W,H = 595.276,841.89
M,CW = 46,503.276
INK,TEAL,PAPER,PALE,GOLD,MUTED,LINE,WHITE,RUST = '#17383E','#087F83','#F7F5F0','#E6EFEB','#B7844C','#597071','#CCD9D3','#FFFFFF','#9B5641'
PAGE=0
BOUNDS=[]
TEXT=[]
ISSUES=[]
c=canvas.Canvas(str(args.output),pagesize=(W,H),pageCompression=1)
c.setTitle('Governed Agent Fabric | The reusable governance system')
c.setAuthor('Governed Agent Fabric project')
c.setSubject('Framework, natural-language design, configurable enforcement, eighteen components and evidence')

def rect(x,y,w,h,fill,stroke=None,r=0):
    c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke or fill))
    if r:c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=bool(stroke))
    else:c.rect(x,H-y-h,w,h,fill=1,stroke=bool(stroke))

def line(x1,y1,x2,y2,color=LINE,width=1,dash=None):
    c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.setDash(dash or [])
    c.line(x1,H-y1,x2,H-y2);c.setDash([])

def circle(x,y,r,fill):
    c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(fill));c.circle(x,H-y,r,fill=1,stroke=0)

def p(text,x,y,w,size=11.25,leading=None,font='Body',color=INK,align=0,record=True):
    obj=Paragraph(text,ParagraphStyle('p',fontName=font,fontSize=size,leading=leading or size*1.35,textColor=HexColor(color),alignment=align,allowWidows=0,allowOrphans=0))
    _,h=obj.wrap(w,1200)
    obj.drawOn(c,x,H-y-h)
    if record:
        BOUNDS.append({'page':PAGE,'x':round(x,2),'y':round(y,2),'w':round(w,2),'h':round(h,2),'text':text[:100]})
        TEXT.append((PAGE,text))
        if y+h>760 and PAGE!=1:ISSUES.append(f'Page {PAGE} overflow at {y+h:.1f}: {text[:90]}')
        if x<20 or x+w>W-20:raise ValueError(f'Page {PAGE} horizontal overflow')
    return h

def label(text,x,y,w=CW,color=TEAL,size=8.5):
    return p(text.upper(),x,y,w,size,size*1.3,'Bold',color)

def arrow(x1,y1,x2,y2,color=TEAL,width=1.4,dash=None):
    line(x1,y1,x2,y2,color,width,dash)
    a=math.atan2(y2-y1,x2-x1)
    for d in (-.5,.5):line(x2,y2,x2-5*math.cos(a+d),y2-5*math.sin(a+d),color,width)

def start(n,section,title,deck,source=''):
    global PAGE
    PAGE=n;rect(0,0,W,H,PAPER)
    label(f'{n:02} / {section}',M,34)
    p(title,M,66,CW,28,33,'Display')
    p(deck,M,147,CW,11.8,15.7,color=MUTED)
    line(M,788,W-M,788)
    p('GOVERNED AGENT FABRIC',M,800,220,8,10,'Bold',MUTED,record=False)
    p(section.upper(),267,800,246,8,10,color=MUTED,align=2,record=False)
    p(f'{n:02}',W-M-22,800,22,9,11,'Bold',TEAL,align=2,record=False)
    if source:p(source,M,769,CW,7.7,10,color=MUTED,record=False)
    c.bookmarkPage(f'p{n}');c.addOutlineEntry(f'{n:02}  {section}',f'p{n}',0,False)

def end():c.showPage()

def band(y,title,body,h=86,fill=INK):
    rect(M,y,CW,h,fill,r=3)
    p(title,M+17,y+13,CW-34,15,19,'Display',WHITE)
    body_height=p(body,M+17,y+40,CW-34,10.6,14.2,color=WHITE)
    if body_height+40>h-6:ISSUES.append(f'Page {PAGE} band text exceeds panel')

def block(title,body,y,x=M,w=CW,size=11.2):
    ht=p(title,x,y,w,12.8,17,'Bold')
    hb=p(body,x,y+ht+7,w,size,size*1.35)
    return ht+hb+22

def step(n,title,body,y,x=M,w=CW):
    circle(x+12,y+13,12,TEAL)
    p(str(n),x,y+5,24,10.8,13,'Bold',WHITE,align=1)
    ht=p(title,x+37,y,w-37,12.6,16.5,'Bold')
    hb=p(body,x+37,y+ht+5,w-37,10.9,14.6)
    return ht+hb+18

def box(x,y,w,h,title,body,fill=WHITE,title_size=12):
    rect(x,y,w,h,fill,r=3)
    ht=p(title,x+13,y+12,w-26,title_size,title_size*1.25,'Bold')
    p(body,x+13,y+ht+21,w-26,10.5,14)

def rows(data,widths,y,headers=None,size=10.2,padding=10,minheight=40):
    if headers:
        rect(M,y,CW,29,INK);xx=M
        for txt,ww in zip(headers,widths):p(txt,xx+padding,y+8,ww-2*padding,8.7,11,'Bold',WHITE);xx+=ww
        y+=29
    for i,row in enumerate(data):
        heights=[]
        for j,(txt,ww) in enumerate(zip(row,widths)):
            ob=Paragraph(txt,ParagraphStyle('measure',fontName='Bold' if j==0 else 'Body',fontSize=size,leading=size*1.33))
            heights.append(ob.wrap(ww-2*padding,1000)[1])
        hh=max(minheight,max(heights)+2*padding)
        rect(M,y,CW,hh,WHITE if i%2==0 else PALE);xx=M
        for j,(txt,ww) in enumerate(zip(row,widths)):
            p(txt,xx+padding,y+padding,ww-2*padding,size,size*1.33,'Bold' if j==0 else 'Body');xx+=ww
        y+=hh
    return y

def component(num,name,question,interaction,binding,evidence,y,h=100):
    rect(M,y,CW,h,WHITE,r=3)
    label(num,M+13,y+13,w=27,size=9)
    title_height=p(name,M+40,y+11,150,12,15,'Bold')
    question_height=p(question,M+40,y+title_height+19,150,10,13)
    right_height=p('<b>Connects:</b> '+interaction+'<br/><b>Configure:</b> '+binding+'<br/><b>Verify:</b> '+evidence,M+207,y+11,CW-220,9.7,12.5)
    if max(title_height+question_height+19,right_height+11)>h-6:
        ISSUES.append(f'Page {PAGE} component card {num} text exceeds card')

S1='Sources: Erdos Effect framework; verified framework crosswalk; repository architecture. Provenance: p24.'
S2='Sources: current configurable source, workflow definitions and tests. Limits and evidence status: pp21-24.'
S3='Sources: component catalogue, configurable-workflows.md and native component evidence. See p22 for status.'

# 01 / Cover
PAGE=1;rect(0,0,W,H,INK);rect(0,0,12,H,TEAL)
label('Collaborator briefing / '+STATUS['date'],M,46,color='#A9D5CC',size=9)
p('Governed<br/>Agent Fabric',M,105,CW,47,51,'Display',WHITE)
p('The reusable<br/>governance system',M,236,CW,26,32,'Display','#BCE1D8')
p('From workflow assessment to enforceable action',M,327,CW,12.4,17,color='#D0DED9')
for yy,col in [(402,'#54867F'),(425,'#6FA59B'),(448,'#A9D5CC')]:
    circle(60,yy,3,col);line(60,yy,165,yy,col,1.2);line(165,yy,221,451,col,1.2)
rect(221,393,159,119,'#224950',r=4)
label('A shared contract',237,410,w=125,color='#BCE1D8')
p('Design<br/>Authority<br/>Evidence',237,433,126,16,20,'Display',WHITE)
arrow(380,451,492,451,'#BCE1D8',1.7);circle(498,451,6,GOLD)
line(498,458,498,546,'#6FA59B',1.2);line(498,546,166,546,'#6FA59B',1.2);arrow(166,546,166,470,'#6FA59B',1.2)
label('Operation teaches the next design',211,558,w=330,color='#9EC7BE',size=8.3)
p('Describe the work. Make its authority explicit.<br/>Carry the evidence through to the effect.',M,615,CW,21,28,'Display',WHITE)
p('A detailed account of the framework we build on, the engineering we add, the eighteen component groups, and the work still required to earn broader use.',M,704,CW,11.5,15.5,color='#D0DED9')
line(M,781,W-M,781,'#456167');p('RESEARCH IMPLEMENTATION + COLLABORATION ROADMAP',M,797,CW,8.5,11,'Bold','#A9D5CC',record=False)
c.bookmarkPage('p1');c.addOutlineEntry('01  Governed Agent Fabric','p1',0,False);end()

# 02 / Proposition
start(2,'The proposition','A workflow is the unit.<br/>A fabric makes it repeatable.',
      'The opportunity is to connect a useful governance design with the authority, controls and evidence needed to put that design into operation.',S1)
y=211
y+=block('What an organisation brings','A process, its purpose, the people and systems involved, the decisions it makes, and the consequences of getting them wrong. It also brings its own policies, owners and operating constraints.',y)
y+=block('What the system should return','A reviewable governance specification and assessment; a versioned package for supported controls; explicit questions and implementation gaps; and a validation plan tied to the workflow. The output can guide an AI agent, a conventional application or a human-led process.',y)
y+=block('What makes this more than a document generator','The same identifiers and contracts continue into execution. A proposed operation has a bounded shape, an accountable actor, current source facts, a defined approval rule and an attributable result. Evidence from operation can then change the next assessment.',y)
band(512,'The reusable core is a chain of responsibility.',
     'Natural language helps describe and design. Reviewed configuration expresses supported rules. The shared fabric checks authority. A registered adapter creates the effect. Evidence shows what actually happened.',h=100)
label('A reading route',M,629)
rows([('The basis','Original framework and extension: pages 3-6'),('The product','Natural-language design, contracts and outputs: pages 7-9'),('The system','Eighteen groups, execution and evidence: pages 10-16'),('The proof','Examples, boundaries, validation and next steps: pages 17-24')],[107,CW-107],651,size=9.8,padding=5,minheight=21)
end()

# 03 / Original framework
start(3,'The framework we extend','Begin with the original<br/>governance problem.',
      'The Erdos framing makes workflow description and governance assessment central. Our extension keeps that foundation visible.',S1)
p('The original approach already reaches beyond identifying risks. It considers authority, controls, implementation, validation and operational evidence. Our contribution should therefore be described as a concrete implementation and generalisation of that intent, with clearer executable contracts and product boundaries.',M,211,CW,11.8,16)
box(M,300,241,191,'The original design obligation','Understand the workflow before judging it. Make purpose, process, authority, information, accountability, obligations and assurance visible. Produce outputs a responsible owner can review and use.',PALE,13)
box(M+261,300,242,191,'The engineering extension','Represent the design in strict data contracts. Bind it to identities, resources, policy, approvals and adapters. Make supported rules enforceable and preserve the distinction between a proposal, an implementation and verified operation.',WHITE,13)
arrow(M+243,394,M+257,394)
y=521
y+=block('Why the input/output work matters','A vague input produces a plausible narrative without enough information to implement or challenge it. A clear contract exposes missing ownership, contradictory limits and unsupported actions before they become hidden assumptions in an agent.',y)
y+=block('What we should preserve','The assessment remains broader than the executable subset. Human impact, legal applicability, proportionality, quality of oversight and acceptance of residual risk cannot be reduced to a successful API response.',y)
p('The next two pages retain source section IDs with concise paraphrases. The engineering representations and eighteen-product selection are our choices; they are not requirements or endorsements from the source author.',M,718,CW,9.9,13.2,color=MUTED)
end()

# 04 / Input crosswalk
start(4,'The seven input areas','From a workflow description<br/>to an assessable record.',
      'Each input area asks a different governance question. Our representation must preserve its source, owner and uncertainty.',S1)
data=[
('3.1.1<br/>Purpose and context','What is the work for, and where does it apply?','Purpose, intended outcomes, jurisdiction, criticality, service and accountable business owner.'),
('3.1.2<br/>Process structure','What happens, in what order, with which exceptions?','Activities, decisions, people, systems, handoffs, source/target boundaries and failure paths.'),
('3.1.3<br/>AI authority','Who can do what, to which resource, under whose authority?','Authenticated principal, permitted operations, resource scope, limits and delegation ceiling.'),
('3.1.4<br/>Information context','Which facts may the decision rely on?','Authoritative source, classification, permitted purpose, freshness, version and quality expectations.'),
('3.1.5<br/>Accountability and impact','Who owns the outcome, and how can it be challenged?','Risk owner, reviewer, affected people, decision rights, escalation and appeal arrangements.'),
('3.1.6<br/>Assessment criteria','Which requirements apply, and who has confirmed that?','Dated supplied requirements, applicability rationale, jurisdiction and unresolved specialist questions.'),
('3.1.7<br/>Safeguards and evidence','How will we know this works and remains acceptable?','Validation criteria, observed evidence, incidents, monitored signals and material change triggers.'),
]
y=rows(data,[111,166,CW-277],211,['INPUT AREA','QUESTION','OUR REPRESENTATION'],size=9.9,padding=9,minheight=65)
p('These are structured evidence-bearing inputs, not seven boxes to tick. Unknown facts stay unknown; assumptions and proposed answers remain distinguishable from supplied information.',M,y+16,CW,10.4,14)
end()

# 05 / Output crosswalk
start(5,'The twelve outputs','What a governance design<br/>must make usable.',
      'The specification is a connected set of decisions and evidence needs. An implementation package is one part of that broader assessment.',S1)
data=[
('4.1  Understanding and gaps','Missing, conflicting and unsupported inputs; questions for the right owner.'),
('4.2  Decision advice','Draft readiness advice and unresolved conditions; authority must be appointed outside the generator.'),
('4.3  Analysis by step','Failure scenarios, control points and tests linked to particular workflow steps.'),
('4.4  Risk records','Proposed scenarios, uncertainty and treatment; residual acceptance reserved for an accountable owner.'),
('4.5  Autonomy boundaries','Proposed authority and review limits; compare these with actual deployed permissions.'),
('4.6  Control designs','Controls and enforcement locations; bind to reviewed configuration and adapters during implementation.'),
('4.7  Requirements traceability','Source/step/risk/control references; applicability and implementation links require review.'),
('4.8  Validation design','Scenarios and proposed measures; executed results and independent review remain separate.'),
('4.9  Operational response','Response and recovery proposals; owners, thresholds and rehearsal evidence remain required.'),
('4.10  Value and restraint','Value hypotheses, missing baselines and costs to measure before increasing autonomy.'),
('4.11  Remediation priorities','Prioritized gaps and control links; actual owners, dates and completion proof must be supplied.'),
('4.12  Assessment history','Versioned draft with source/content identities; retain approval decisions and later evidence separately.'),
]
y=rows(data,[165,CW-165],211,['SOURCE AREA (PARAPHRASE)','OUR ARTIFACT + REQUIRED REVIEW'],size=9.8,padding=7,minheight=34)
p('This draft organizes claims and proposals. People must verify the interpretation and supply missing decisions and evidence; traceability is not certification.',M,y+16,CW,10.3,13.8)
end()

# 06 / Original-to-extension diagram
start(6,'Our contribution','Keep the framework.<br/>Make its contracts executable.',
      'The extension is a bridge between workflow assessment and a repeatable operating system for bounded action.',S1)
layers=[
    (211,'WORKFLOW + GOVERNANCE FRAMEWORK','Purpose, process, authority, information, accountability, obligations, assurance',PALE),
    (314,'DESIGN AND ASSESSMENT CONTRACT','Evidence-grounded inputs; explicit unknowns; control design; twelve connected outputs',WHITE),
    (417,'IMPLEMENTATION CONTRACT','Reviewed workflow definitions; operation schemas; policy bindings; adapter requirements',PALE),
    (520,'SHARED ENFORCEMENT + EVIDENCE','Independent authority checks; exact approval; controlled effects; records and feedback',WHITE),
]
for y,title,body,fill in layers:
    rect(M,y,CW,79,fill,r=3);label(title,M+15,y+13,w=CW-30);p(body,M+15,y+37,CW-30,11.2,15)
for y in (291,394,497):arrow(M+251,y,M+251,y+19)
line(M+484,600,M+484,628,TEAL,1.4,[3,3]);line(M+484,628,M-13,628,TEAL,1.4,[3,3]);line(M-13,628,M-13,306,TEAL,1.4,[3,3]);arrow(M-13,306,M+76,306,TEAL,1.4,[3,3])
p('Evidence return: review the assumptions, controls and permission to operate after outcomes, incidents or material changes.',M+44,645,CW-66,10.5,14.2,color=MUTED)
band(681,'The distinction is implementation depth.',
     'We add strict interfaces, reusable integration, tested enforcement behavior and a deliberate engineering path from a reviewed draft to a bounded running system.',h=78)
end()

# 07 / Natural-language design pipeline
start(7,'Natural-language design','Describe the workflow.<br/>Keep the reasoning inspectable.',
      'The design agent should help turn an incomplete description into a source-linked draft, while asking for information that determines the governance design.',S2)
nodes=[('01  Capture','Workflow narrative and supplied source excerpts; preserve provenance.'),('02  Structure','Map inputs, steps, actors, decisions and information flows.'),('03  Question','Identify missing authority, conflicting limits and unsupported assertions.'),('04  Propose','Draft controls, boundaries, review rules and an assessment with explicit gaps.'),('05  Validate','Check schema, cross-references, quoted sources and human-owner boundaries.'),('06  Review','People accept or revise the design; activation remains a separate authority.')]
for i,(title,body) in enumerate(nodes):
    xx=M+(i%2)*261;yy=211+(i//2)*120
    box(xx,yy,242,96,title,body,PALE if i%2==0 else WHITE,12.4)
    if i%2==0:arrow(xx+244,yy+48,xx+257,yy+48)
arrow(M+382,310,M+382,326);line(M+382,326,M+120,326,TEAL,1.3);arrow(M+120,326,M+120,329)
arrow(M+382,430,M+382,446);line(M+382,446,M+120,446,TEAL,1.3);arrow(M+120,446,M+120,449)
p('<b>A prompt is an interface, not an authority.</b> The model can suggest an approval threshold, describe an adapter or identify a missing policy. It cannot turn the suggestion into an approved rule, register code, provision identities or mark a deployment accepted.',M,589,CW,11.2,15)
p('<b>What useful uncertainty looks like:</b> "The process says a manager approves access, but no manager role or authoritative directory is supplied. Please identify the approver and source." That is stronger than silently inventing an owner or threshold.',M,660,CW,11.2,15)
p(escape(STATUS['designer']),M,716,CW,9.9,13.1,color=MUTED)
end()

# 08 / Grounding and questions
start(8,'The design contract','A helpful draft makes<br/>its unknowns visible.',
      'A governance design needs an evidence boundary as much as an execution agent needs an action boundary.',S2)
rows([
('Supplied statement','"The service owner requires two-hour access."','Link the quoted source. Presence proves the words were supplied; it does not prove their truth.'),
('Proposed control','"Require review for privileged access."','Explain the rationale and seek an accountable decision; do not call it existing policy.'),
('Unresolved question','"Which directory proves employee status?"','Keep the missing fact visible and block dependent readiness claims.'),
('Unsupported capability','"Revoke access in the live directory."','Name the missing adapter, delivery contract and verification; do not emit executable fiction.'),
('Observed evidence','"This version passed a negative authorization test."','Attach the actual evidence identity and scope; do not extrapolate to other versions or deployments.')
],[111,173,CW-284],211,['INFORMATION TYPE','EXAMPLE','HOW IT IS USED'],size=10,padding=9,minheight=71)
y=609
y+=block('Questions should be ordered by consequence','First resolve the purpose, permitted effect, owner, identity, source of truth and target. Then settle decision limits, exceptions, oversight and recovery. A design can make progress while these questions remain open, but it must not conceal the dependencies.',y)
p('The human-review boundary is intentional. A well-formed answer may still be factually wrong, contextually inappropriate or legally inapplicable. Schema checks do not replace expert review.',M,717,CW,10.4,14,color=MUTED)
end()

# 09 / Outputs and compilation
start(9,'What the system produces','A specification for people.<br/>A package for supported controls.',
      'Engineering work connects these outputs. A natural-language draft is not automatically compiled into an executable workflow.',S2)
box(M,211,242,193,'The reviewable design','The designer records an initial, non-exhaustive workflow graph, evidence links, proposed risks and controls, questions and an assessment. Accountable reviewers check the interpretation and settle the design.',PALE,14)
box(M+261,211,242,193,'The implementation package','A separate exporter packages validated definitions: typed operations, resource checks, approval predicates, lifetime budgets, adapter identifiers and a disabled deployment manifest.',WHITE,14)
arrow(M+243,307,M+257,307)
rect(M,430,CW,103,INK,r=3)
label('The engineering implementation boundary',M+16,444,w=CW-32,color='#BCE1D8')
p('Supported + valid + reviewed does not mean activated.',M+16,468,CW-32,15,19,'Display',WHITE)
p('Only capabilities represented by validated contracts and registered adapters can become runnable. A deployment owner approves and commissions the resulting package separately.',M+16,497,CW-32,10.6,14.2,color=WHITE)
y=559
y+=block('A concrete example','"Manager approval for admin access" can become a configured predicate and reviewer role once the policy and identity mapping are supplied. "Revoke all downstream credentials after an incident" needs supported target operations, reliable delivery and recovery behavior before it is executable.',y)
y+=block('A concrete output gap','The report should say which requirement is covered, which configuration field expresses it, and what evidence is still needed. If a requirement exceeds the current schema, it remains an explicit gap and a development item.',y)
end()

# 10 / full architecture diagram
start(10,'The eighteen-component fabric','Different authorities.<br/>One controlled effect boundary.',
      'The component groups cooperate across several layers. They are not eighteen interchangeable checks or eighteen steps on every request.',S3)
rect(M,211,CW,59,INK,r=3)
label('Design / review / application layer',M+15,223,w=CW-30,color='#BCE1D8')
p('Workflow narrative -> governance design -> approved implementation contract',M+15,245,CW-30,10.8,14,color=WHITE)
arrow(M+251,273,M+251,294)
layers=[
    (299,'PROPOSE + COORDINATE','18 Ollama / Qwen   |   02 Microsoft AGT   |   05 Temporal',WHITE),
    (373,'ESTABLISH AUTHORITY','01 Keycloak   |   04 OpenFGA   |   03 OPA',PALE),
    (447,'SUPPLY GOVERNANCE + ASSURANCE','06 CISO Assistant   |   07 OpenMetadata   |   08 MLflow   |   15 Fairlearn',WHITE),
    (521,'ENFORCE + COMMIT','Our gateway and reviewed adapter   |   14 PostgreSQL',PALE),
    (595,'OBSERVE + RESPOND','10 OpenTelemetry   |   11 Prometheus / Alertmanager   |   12 DFIR-IRIS   |   13 GLPI',WHITE),
]
for yy,title,body,fill in layers:
    rect(M,yy,CW,59,fill,r=3);label(title,M+14,yy+10,w=CW-28,size=8.1);p(body,M+14,yy+31,CW-28,10.1,13.1)
for yy in (361,435,509,583):arrow(M+251,yy,M+251,yy+9)
rect(M,679,CW,62,INK,r=3)
label('Protected deployment spans every layer',M+14,691,w=CW-28,color='#BCE1D8',size=8.2)
p('09 OpenBao   |   16 Kubernetes / Cilium   |   17 Syft / Grype / Cosign',M+14,713,CW-28,10.8,14,color=WHITE)
end()

# Remaining pages are deliberately explicit editorial content, not generated
# marketing claims. Status overrides above keep validation claims easy to update.

# 11 / authority components
start(11,'Authority and coordination','Five questions before<br/>an action can proceed.',
      'These groups separate the proposal, the authenticated actor, the resource relationship, the policy decision and the durable wait for review.',S3)
components=[
('01','Keycloak','Who is presenting this request?','A signed identity reaches the gateway; its principal mapping selects server-owned roles and tenant.','Issuer, subject mapping and allowed principals.','Expired, wrong-scope and unmapped identities are rejected.'),
('02','Microsoft Agent Governance Toolkit','Which tools may the agent attempt to call?','An interceptor restricts the exposed operation set; the gateway independently evaluates each effect.','Operation allowlist and integration binding.','Unknown tools and disallowed calls fail; in-process interception is not isolation.'),
('03','Open Policy Agent','Does current policy permit this proposed operation?','The gateway supplies trusted context and the approved configuration digest; an allow cannot override a local denial.','Reviewed policy data, restrictions and tenant scope.','Wrong digest, missing decision or unavailable policy denies the write.'),
('04','OpenFGA','Does this actor have the required relationship to this resource?','Checks use a scoped resource identity combining workflow, tenant and resource, avoiding ambiguous names.','Subject/object types, relations and commissioned tuples.','Cross-resource and cross-tenant relationships cannot substitute for one another.'),
('05','Temporal','How does this request survive waiting and restart?','A durable workflow can wait for review and retry the governed gateway using the same exact action.','Task queue, worker delegation and workflow entry point.','Restart preserves intent; a signal alone does not manufacture valid approval.'),
]
for i,values in enumerate(components):component(*values,211+i*106,h=100)
end()

# 12 / governance and assurance components
start(12,'Governance, data and models','Know what the decision<br/>is allowed to rely on.',
      'An authorized operation can still be based on unsuitable information or an unvalidated model. These components address different parts of that problem.',S3)
components=[
('06','CISO Assistant Community','Who owns the risk, treatment and acceptance?','Risk/control records receive scoped evidence links; accountable people retain the decision to accept residual risk.','Owner, risk and control identifiers; evidence routing.','An event reaches the intended record and does not auto-close a risk.'),
('07','OpenMetadata','Is the source understood, owned and suitable?','The authority layer checks selected metadata facts such as owner and classification before using a source.','Entity mapping, classification and required metadata.','Missing or mismatched metadata denies selected gates; content truth needs its own validation.'),
('08','MLflow','Which model release and evaluation are being considered?','A selected model gate checks registered release prerequisites and configured metric bounds.','Model/version identity, metrics and promotion process.','Missing or nonfinite metrics fail; served-model provenance needs additional binding.'),
('15','Fairlearn','How do measured outcomes vary between relevant groups?','Process-specific evaluation produces evidence that reviewers can relate to the workflow and model release.','Representative dataset, groups, metrics and review criteria.','The supplied evaluation is reproducible; metric results alone do not establish fairness.'),
]
for i,values in enumerate(components):component(*values,211+i*110,h=103)
p('These records answer complementary questions. Data classification is not data correctness; a model metric is not workflow effectiveness; a risk record is not risk acceptance. The design must name the required evidence for each claim.',M,676,CW,11.1,15)
end()

# 13 / records and operations
start(13,'Records and operations','An effect should leave<br/>more than a chat response.',
      'Receipts establish outcomes. Operational signals reveal faults. Incident and service records turn those observations into accountable action.',S3)
components=[
('14','PostgreSQL','What state changes must agree at commit time?','The generic schema stores scoped resources, approvals, actions, usage, audit and delivery outbox.','Database operations, isolation, retention and recovery.','Effect, approval consumption and evidence commit together for transactional targets.'),
('10','OpenTelemetry Collector','What happened across service boundaries?','Minimized traces connect gateway and downstream operations without placing tokens or unnecessary personal data in telemetry.','Allowed fields, exporters and correlation conventions.','The expected spans arrive and sensitive fields remain absent.'),
('11','Prometheus + Alertmanager','When should an operator know that something is wrong?','Metrics and alert routes expose service failure, control unavailability and selected operational conditions.','Signals, thresholds, ownership and routing.','An injected failure raises the intended actionable alert.'),
('12','DFIR-IRIS','How is a security or governance incident investigated?','Incident delivery links a denied or anomalous event to a scoped case and a response owner.','Customer scope, incident rules and correlation IDs.','Delivery is attributable and retry-safe; responders can trace the source event.'),
('13','GLPI','Which service or asset is affected, and who fixes it?','Inventory bindings provide service context; remediation tickets link gaps to owners and acceptance evidence.','Service type, entity, asset and remediation routing.','The right service and ticket are updated, with verified completion conditions.'),
]
for i,values in enumerate(components):component(*values,211+i*106,h=100)
end()

# 14 / protected deployment
start(14,'Protected deployment','Protect the machinery<br/>that enforces the rules.',
      'Governance is weakened if the model can obtain target secrets, bypass the gateway or run an unreviewed release.',S3)
components=[
('09','OpenBao','Where do service credentials live?','Authorized service identities retrieve scoped secrets; workflow definitions and model context contain no target credentials.','Secret paths, access policies, rotation and service identity.','Unauthorized callers cannot retrieve secrets; rotation and failure behavior are tested.'),
('16','Kubernetes + Cilium','Which workloads may communicate or exercise privilege?','Runtime isolation and network rules protect the exclusive gateway/adapter path and constrain lateral access.','Service accounts, containers, network routes and cluster policy.','Bypass, unauthorized egress and privilege escalation tests fail as intended.'),
('17','Syft + Grype + Cosign','What did we build, what is inside it, and can we verify it?','Inventory, vulnerability and signature checks attach release evidence to the actual deployable artifact.','Build inputs, vulnerability policy, signer and verification gate.','A tampered, unsigned or disallowed release cannot pass the configured gate.'),
('18','Ollama + Qwen','How are candidate tool calls proposed?','The bounded agent receives task-derived tool schemas; its proposal crosses the authenticated gateway before any effect.','Inference endpoint, model, limits and prompt behavior.','Unknown tools, changed intent and fabricated success cannot produce an executed receipt.'),
]
for i,values in enumerate(components):component(*values,211+i*110,h=103)
p('These deployment controls are essential to the intended architecture, but the generic branch is an opt-in development path. Existing lab manifests and recorded native evidence must not be mistaken for acceptance of this new deployment.',M,676,CW,11.1,15)
end()

# 15 / sequence diagram
start(15,'Execution and approval','Approval is a bound decision.<br/>Execution is a fresh check.',
      'The gateway owns identity and task intent. The model can propose the operation; an independent reviewer may authorize its exact scope.',S2)
xs=[M+46,M+184,M+321,M+457]
titles=['Agent / client','Gateway + state','Reviewer','Target adapter']
for xx,title in zip(xs,titles):
    rect(xx-46,211,92,43,INK,r=3);p(title,xx-40,221,80,10.2,13.2,'Bold',WHITE,align=1)
    line(xx,259,xx,654,LINE,1,[3,3])
events=[
(0,1,288,'1  Bound task + inspect'),
(0,1,344,'2  Propose exact action'),
(1,0,391,'3  Review required; no effect'),
(2,1,438,'4  Approve stored exact intent'),
(0,1,485,'5  Retry same action'),
(1,3,571,'7  Apply permitted effect'),
(3,1,617,'8  Receipt + atomic evidence'),
(1,0,657,'9  Return authoritative result'),
]
for a,b,yy,title in events:
    arrow(xs[a],yy,xs[b],yy,TEAL,1.3)
    left=min(xs[a],xs[b]);ww=max(abs(xs[a]-xs[b]),126)
    p(title,left+3,yy-25,ww-6,8.9,11.4,'Bold')
rect(xs[1]-59,510,118,38,PALE,r=3)
p('6  Recheck authority,<br/>context, limits and TTL',xs[1]-54,517,108,8.7,11.1,'Bold',align=1)
p('<b>Bound together:</b> complete action, actor state, source state, configuration fingerprint and deployment approval. Changed context or revoked authority prevents a new effect. A completed retry retrieves a historical receipt.',M,696,CW,10.6,14.3)
end()

# 16 / evidence diagram
start(16,'Evidence and reassessment','Close the loop<br/>without inventing assurance.',
      'The design becomes stronger when its claims can be traced to the configuration, tests and events that support them.',S2)
nodes=[
(M,211,'Requirement / risk','Why this control is needed; owner and supplied basis.'),
(M+261,211,'Control / configuration','Which rule enforces it; version and content fingerprint.'),
(M+261,353,'Test / validation','Which positive and negative cases establish the expected behavior.'),
(M+261,495,'Event / receipt','What happened in operation; exact action and decision context.'),
(M,495,'Incident / remediation','What failed, who responds, and what proves the fix.'),
(M,353,'Reassessment / release','Which assumptions or approvals must change before reuse.'),
]
for x,y,title,body in nodes:box(x,y,242,103,title,body,WHITE if x==M else PALE,12.4)
arrow(M+244,262,M+257,262);arrow(M+382,317,M+382,348);arrow(M+382,459,M+382,490)
arrow(M+257,546,M+245,546);arrow(M+121,490,M+121,460);arrow(M+121,348,M+121,318)
band(629,'A useful evidence link is specific.',
     'Name the workflow, configuration digest, adapter and product versions, test scope, decision and operating environment. Passing a different version or another deployment does not close this claim.',h=91)
p('The audit chain detects local modification. Independent retention, signed checkpoints, access controls and recovery verification remain deployment responsibilities. Delivery to a risk system is not automatic risk acceptance.',M,733,CW,9.8,13.1,color=MUTED)
end()

# 17 / credit story
start(17,'Story 1 / synthetic credit','A £200 request becomes<br/>a reviewable commitment.',
      'This shipped example demonstrates the common runtime and transactional synthetic target. It does not make a real lending decision.',S2)
rect(M,211,CW,72,PALE,r=3);label('The supplied action',M+15,224)
p('<b>case-a</b> / commit_credit / <b>20,000 pence (£200)</b><br/>Trusted resource: KYC clear; region UK. Permitted acting role: agent.',M+15,246,CW-30,11.2,15)
stories=[
('Inspect the source','The task-bound read obtains current stored facts. The model cannot provide its own KYC result, identity or approval status as trusted context.'),
('Pause for independent review','The configured rule requires review above £100. The £200 request returns approval_required; no ledger effect or budget usage has been committed.'),
('Bind approval to this decision','A separate reviewer approves this exact action and its context. The example approval expires after five minutes and cannot override blocked source facts or exhausted budgets.'),
('Recheck and commit','The gateway rechecks current authority, source, configuration, stop state, task validity and aggregate limits. The local effect, usage, approval consumption, audit and outbox commit together.'),
('Retry without duplicating','The same scoped idempotency key and unchanged action return the original receipt. A different amount with that key is rejected. This property applies to the local transactional target.'),
]
for i,(title,body) in enumerate(stories):step(i+1,title,body,310+i*81)
p('<b>Illustrative limits:</b> £1,000 per resource and £5,000 per tenant, as lifetime usage counters. A real product needs its own policy, customer impact assessment, data quality and lending validation.',M,725,CW,10.2,13.7,color=MUTED)
end()

# 18 / access story
start(18,'Story 2 / IT access','The same engine governs<br/>a different kind of effect.',
      'A four-hour admin-access request changes the operation schema, policy and adapter, while reusing the control path.',S2)
rect(M,211,CW,72,PALE,r=3);label('The supplied action',M+15,224)
p('<b>employee-a</b> / grant_access / <b>admin for four hours</b><br/>Trusted resource: active employee; approved application.',M+15,246,CW-30,11.2,15)
stories=[
('Describe the consequence','The parameters are permission, duration and justification. There is no monetary amount or credit-case assumption in the shared runtime.'),
('Apply this workflow\'s rules','Admin permission OR a duration above eight hours requires review. Four hours still needs approval because the permission is privileged. An inactive employee remains a hard denial.'),
('Review within the right context','The reviewer must be a different permitted principal in the same tenant. This profile uses a three-minute approval and one-hour source freshness window.'),
('Use the registered target adapter','The synthetic access adapter records a directory grant and an expiry timestamp within the transaction. It does not change a real directory or prove scheduled revocation.'),
('Interpret the evidence precisely','An executed receipt proves the local configured effect and its control path. Live access provisioning, revocation, entitlement reconciliation and human oversight still need independent acceptance.'),
]
for i,(title,body) in enumerate(stories):step(i+1,title,body,310+i*81)
p('<b>What was reused:</b> schema checking, identity, source freshness, deployment approval, stop state, exact approval binding, budget accounting, retries and evidence. The profile and adapter supply the specialization.',M,725,CW,10.2,13.7,color=MUTED)
end()

# 19 / unrelated domain
start(19,'Story 3 / a museum loan','An unrelated process.<br/>The same design discipline.',
      'A synthetic designer input tests whether a different set of actors, restrictions and conditional paths remains visible. It supplies no execution adapter.',S2)
p('The assistant reads a loan request, catalogue entry and conservation report, then drafts a suitability summary and checklist. A conservator assesses condition; the registrar checks availability, insurance and transport; the lending committee makes the loan decision.',M,211,CW,11.6,15.8)
rows([
('Authority boundary','The assistant may prepare documents. It cannot approve a loan, sign an agreement, reveal the storage location or instruct a courier.'),
('Conditional paths','Missing conservation evidence keeps the case pending; conflicting dates go to the registrar; cancellation records a reason. After approval, the registrar schedules handover and return checks.'),
('Data and sources','The request, catalogue and conservation report have distinct roles. Precise storage locations are restricted to authorized staff. A catalogue API has not been selected.'),
('Questions to resolve','Retention, exception authority, actual API permissions and representative evaluation remain unspecified. Faster preparation is an expected benefit with no measured baseline.'),
('Implementation gaps','Source ingestion, reviewed preparatory operations, authorized target integration and acceptance tests remain engineering work. Human loan authority stays with the designated committee.'),
],[125,CW-125],292,['DESIGN ELEMENT','WHAT THE DESIGNER SHOULD SURFACE'],size=10.3,padding=10,minheight=66)
p('<b>The test of reuse:</b> preserve this input\'s human decision boundary and exception paths, without importing credit limits or access-grant logic. A source-linked draft remains subject to review; it cannot expand the assistant\'s authority.',M,691,CW,11.1,15)
end()

# 20 / configuration boundary
start(20,'The boundary of reuse','Change the workflow package.<br/>Extend only what is missing.',
      'A reusable platform does not mean that every future requirement is already implemented. It means the change has a clear, contained home.',S2)
data=[
('Change a review threshold','Configuration / policy','Update a supported predicate; review, version, test and approve the new definition.'),
('Add another supported workflow','Workflow package','Supply resource and action schemas, source checks, roles, review rules, limits and bindings.'),
('Use different product instances','Deployment bindings','Commission identity, relationship, source, model, inventory, evidence and secret mappings.'),
('Introduce a new local effect','Registered adapter','Implement the transactional adapter contract; verify validation, atomic effect and evidence behavior.'),
('Call a real external system','Integration capability','Add target idempotency, conditional updates, durable delivery, receipts and uncertain-outcome reconciliation.'),
('Express an unsupported control','Shared capability extension','Extend the contract and engine with review and tests; do not smuggle arbitrary code into configuration.'),
]
y=rows(data,[129,123,CW-252],211,['NEED','WHERE IT BELONGS','WHAT MUST HAPPEN'],size=10.1,padding=9,minheight=67)
p('<b>Current contract limits:</b> bounded primitive object fields, supported predicates and positive integer lifetime budgets. General workflow-graph execution, arbitrary expressions, nested parameter structures and rolling budgets are not implied capabilities.',M,y+19,CW,10.9,14.6)
p('The eighteen products are reusable capability providers. Our contracts and integration determine how they cooperate for this process. A new workflow should not require rewriting all eighteen products.',M,717,CW,10.5,14.1,color=MUTED)
end()

# 21 / failure cases
start(21,'Validation that matters','Test the boundary<br/>by trying to cross it.',
      'A positive demonstration is necessary. Negative and change-of-state tests establish whether the governance boundary holds when it is challenged.',S2)
data=[
('Invent authority','Model adds actor, role, approval or target URL.','Strict envelopes reject it; identity and targets remain server-owned.'),
('Substitute intent','Change resource, parameters or workflow after task creation.','Task binding rejects the proposal; no target effect.'),
('Reuse stale approval','Change source, actor state, configuration or reviewer authority.','A new effect requires a currently valid exact approval.'),
('Wait past expiry','Queue a request or delay a policy call until its task expires.','Recheck under the execution transaction and before effect; deny.'),
('Race the budget','Two actors contend for the remaining shared limit.','Serialized checks prevent both actions spending the same remaining budget.'),
('Lose a dependency','Selected policy or context authority is unavailable.','Fail closed for the selected gate; do not silently substitute old facts.'),
('Repeat the request','Retry an already completed operation after uncertainty.','Return the prior matching receipt; reject a changed payload with the same key.'),
('Break evidence delivery','A downstream risk or incident sink fails.','Retain the outbox event and delivery state; retry with scoped correlation.'),
]
y=rows(data,[106,184,CW-290],211,['CHALLENGE','EXAMPLE','EXPECTED RESULT'],size=9.9,padding=8,minheight=51)
p('Separate validation is still needed for process correctness, quality of human review, model behavior, representative outcomes, native product operation, recovery and containment. Passing control tests does not answer every governance question.',M,y+18,CW,10.5,14.1)
end()

# 22 / evidence status
start(22,'Evidence and readiness','Be ambitious about the system.<br/>Be precise about the proof.',
      'Described, implemented, tested and observed are distinct assurance levels. We retain that distinction across the framework, code and deployment.',S3)
blocks=[
('FRAMEWORK + DESIGN','A traceable basis','The original framework and repository interpretation define the assessment areas. The configurable implementation represents supported controls and unresolved gaps; design generation never grants production approval.'),
('LOCAL ENGINE + INTERFACES','A testable common path',STATUS['tests']),
('NATURAL-LANGUAGE DESIGN','A developing design capability',STATUS['designer']),
('NATIVE SYSTEM + DEPLOYMENT','A separate acceptance programme',STATUS['native']),
]
for i,(tag,title,body) in enumerate(blocks):
    yy=211+i*108;rect(M,yy,CW,100,WHITE,r=3);label(tag,M+14,yy+11,w=CW-28,size=8.1)
    p(title,M+14,yy+31,166,13.2,17.1,'Display')
    body_height=p(body,M+194,yy+31,CW-209,10.4,14)
    if body_height>63:ISSUES.append(f'Page {PAGE} status card {tag} text exceeds panel')
p('<b>Keep the evidence generations separate:</b> the original native subset observed real model/tool calls in a credit laboratory. New PostgreSQL evidence covers the generic workflows. OpenMetadata, DFIR-IRIS and GLPI remain uncommissioned; cluster isolation and the High-severity supply-chain gate remain unresolved. None of these observations establishes simultaneous all-eighteen acceptance.',M,663,CW,10.5,14.1)
p(escape(STATUS['release']),M,736,CW,9.8,13.1,color=MUTED)
end()

# 23 / next work
start(23,'The route to useful deployment','Earn wider use<br/>one explicit gate at a time.',
      'The next collaboration should produce decisions, testable artifacts and evidence, rather than a broader unqualified claim.',S2)
roadmap=[
('Agree the workflow and owners','A business owner supplies a bounded process, consequence and source of truth. Governance reviewers confirm decision rights, questions, applicability and the evidence required.'),
('Review the generated design','Compare the draft with supplied sources. Resolve or assign unknowns. Distinguish proposed controls from existing policy, and supported configuration from implementation work.'),
('Qualify the common engine and adapters','Run the positive, negative and change-of-state cases for the selected profiles and adapter versions. Review the contracts and business-effect boundary independently.'),
('Commission the actual product bindings','Prove identity, relationships, source/model gates, risk/evidence routes, workload isolation, secrets and the built release in the chosen environment.'),
('Accept a bounded pilot and learn from it','Name stop authority, operating limits, incident response and manual fallback. Validate recovery and uncertain outcomes. Reassess after material changes or adverse evidence.'),
]
for i,(title,body) in enumerate(roadmap):step(i+1,title,body,211+i*88)
band(679,'The next useful agreement',
     'Choose one real workflow, one accountable owner and one constrained effect. Agree which evidence would justify a pilot, and which findings would stop it.',h=76)
end()

# 24 / provenance and practical reading
start(24,'Provenance and use','A document that can<br/>be challenged and updated.',
      'This briefing is an architecture and implementation account. Its sources, examples and status boundaries are intentionally visible.',
      'Prepared '+STATUS['date']+'. Editable source: scripts/build_generalisation_briefing.py. Vector diagrams are original to this briefing.')
article='https://www.linkedin.com/pulse/implementing-governance-agentic-workflows-erdos-effect-vipie'
repo='https://github.com/CodeDaim0n/AI-governance-repo'
p('<b>1 / Framework source.</b> Erdos Effect, <i>Implementing Governance for Agentic Workflows</i>, published 1 November 2026. The full public article was verified during this task. Section IDs preserve the crosswalk; labels here are short paraphrases and engineering interpretations, not a reproduction of the article.',M,211,CW,10.6,14.3)
p(f'<link href="{article}" color="{TEAL}">Read the original framework article</link>',M,287,CW,10.3,14)
p('<b>2 / Original implementation and evidence.</b> The research repository at commit <b>098f75fb1be3</b> supplies the original architecture, component catalogue, native laboratory records and explicit incomplete-stack status. Earlier component observations do not qualify the new generic path.',M,324,CW,10.6,14.3)
p(f'<link href="{repo}/tree/098f75fb1be3c44e655d1f7e535eb0a3016f0885" color="{TEAL}">Open the pinned research repository</link>',M,389,CW,10.3,14)
p('<b>3 / Configurable development snapshot.</b> The current checkout supplies the configurable implementation and designer. Read docs/framework-extension-map.md and docs/configurable-workflows.md. Regression records: results/designer-validation/. Model trials: results/workflow-designer/. Newer storage evidence: results/native-postgres/20261102T093819Z/summary.json.',M,426,CW,10.6,14.3)
p('<b>4 / How to read the examples.</b> Credit and access use synthetic local effects. The museum story follows examples/workflow-descriptions/museum-loan.txt: the assistant prepares documents while people retain loan authority. It does not assert a museum adapter, domain validation or production operation.',M,502,CW,10.6,14.3)
p('<b>5 / How to update this briefing.</b> The editable Python source contains every diagram and page. A single status object, or an optional status JSON file, updates evidence statements. Regenerate the PDF, render every page, inspect layout and confirm that new claims point to the corresponding evidence.',M,578,CW,10.6,14.3)
band(666,'The promise we can make responsibly',
     'A clearer path from workflow to governance design, and from supported design to controlled execution - with reusable components, explicit extension points and evidence that states its limits.',h=88)
end()

c.save()
(args.work/'layout-bounds.json').write_text(json.dumps(BOUNDS,indent=2),encoding='utf-8')
(args.work/'briefing-text.txt').write_text('\n\n'.join(f'[Page {page}] {text}' for page,text in TEXT),encoding='utf-8')
(args.work/'status-used.json').write_text(json.dumps(STATUS,indent=2),encoding='utf-8')
(args.work/'layout-issues.json').write_text(json.dumps(ISSUES,indent=2),encoding='utf-8')
print(args.output)
print(f'Pages: {PAGE}; text objects: {len(BOUNDS)}')
if ISSUES:
    print('\n'.join(ISSUES))
    raise SystemExit(1)
