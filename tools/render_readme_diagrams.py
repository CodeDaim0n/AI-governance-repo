"""Generate exact, accessible SVG architecture artwork for the GitHub landing page."""
from pathlib import Path
from html import escape
import textwrap,json
from PIL import ImageFont
R=Path(__file__).resolve().parents[1];OUT=R/'docs/assets'
INK='#172d46';TEAL='#087f8c';MUTED='#51657a';PURPLE='#7656a6';ORANGE='#b76c20'
class SVG:
 def __init__(self,w,h,title,desc):
  self.w=w;self.h=h;self.seen=set()
  self.parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc><defs>']
  for name,color in [('flow',INK),('context',PURPLE),('observe',TEAL),('review',ORANGE)]:
   self.parts.append(f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="{color}"/></marker>')
  self.parts+=['</defs><rect width="100%" height="100%" rx="20" fill="#ffffff"/>']
 def rect(self,x,y,w,h,fill='#ffffff',stroke='none',radius=10):
  self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')
 def text(self,x,y,text,size=18,color=INK,weight=400):
  self.parts.append(f'<text x="{x}" y="{y}" font-family="DejaVu Sans,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(text)}</text>')
 def path(self,points,kind='flow',both=False,dash=False):
  color={'flow':INK,'context':PURPLE,'observe':TEAL,'review':ORANGE}[kind]
  self.parts.append('<path d="'+ ' '.join(('M' if i==0 else 'L')+str(x)+' '+str(y) for i,(x,y) in enumerate(points))+'" fill="none" stroke="'+color+'" stroke-width="2.3" stroke-linejoin="round"'+(' stroke-dasharray="7 5"' if dash else '')+f' marker-end="url(#{kind})"'+(f' marker-start="url(#{kind})"' if both else '')+'/>')
 def lane(self,y,label,fill):
  self.rect(34,y-50,1132,208,fill)
  self.text(50,y-20,label,16,MUTED,700)
 def card(self,x,y,n,title,lines,color=TEAL,own=False,w=344,h=160):
  if n is not None:self.seen.add(n)
  fill=INK if own else '#ffffff';body='#d8e4ef' if own else MUTED;head='#ffffff' if own else INK
  self.rect(x,y,w,h,fill,INK if own else '#d3dfe8')
  self.rect(x,y,6,h,color,radius=3)
  if n is not None:
   self.rect(x+16,y+18,34,29,color,radius=6);self.text(x+20,y+39,f'{n:02}',17,'#ffffff',700);tx=x+62
   self.parts.append(f'<g data-component-id="{n:02}"><title>{n:02} {escape(title)}</title></g>')
  else:tx=x+18
  fs=20
  while ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',fs).getlength(title)>w-(tx-x)-16:fs-=1
  self.text(tx,y+40,title,fs,head,700)
  for i,line in enumerate(lines):self.text(x+18,y+76+i*25,line,18,body)
  if own:self.text(x+18,y+h-13,'PROJECT IMPLEMENTATION',11,'#8bcbd1',700)
 def save(self,name):
  p=OUT/name;p.write_text(''.join(self.parts)+'</svg>');return p

def architecture():
 s=SVG(1200,1880,'Governed Agent Fabric: all 18 components','An implementation architecture showing every numbered component, its role, the execution gateway, target adapter and evidence delivery. Solid arrows show execution; dashed connections show authority context and operational feedback.')
 s.rect(0,0,1200,145,INK,radius=16)
 s.text(48,48,'ERDOS FRAMEWORK · OUR IMPLEMENTATION APPROACH',16,'#8dd8d6',700)
 s.text(48,94,'Governed Agent Fabric',36,'#ffffff',700)
 s.text(48,126,'18 named component groups · explicit authority, action and evidence',18,'#c9dce9')
 rows=[(210,'GOVERNANCE & AUTHORITATIVE RECORDS','#f1f5fa'),(440,'EVALUATION & RELEASE ASSURANCE','#f5f1fa'),(670,'IDENTITY, RELATIONSHIPS & SECRETS','#f1f6fa'),(900,'AGENT BOUNDARY & POLICY ENFORCEMENT','#eef7f7'),(1130,'PROPOSAL, AUTHORIZATION & HUMAN REVIEW','#eef7f7'),(1370,'CONTROLLED TARGET COMMIT & EVIDENCE','#f1f5fa'),(1600,'OBSERVABILITY & INCIDENT RESPONSE','#fff6ec')]
 for y,label,fill in rows:s.lane(y,label,fill)
 # Draw routed connections before cards, with no line passing through a card.
 for x in [220,600,980]:s.path([(x,370),(x,400),(1180,400)],'context',dash=True)
 s.path([(1180,400),(1180,1090),(600,1090),(600,1130)],'context',dash=True)
 s.path([(392,520),(428,520)],'observe')
 s.path([(600,600),(600,630),(1180,630)],'context',dash=True)
 s.path([(1152,520),(1180,520)],'context',dash=True)
 for x in [220,600,980]:s.path([(x,830),(x,860),(1180,860)],'context',dash=True)
 s.path([(980,1060),(980,1090),(1180,1090)],'context',dash=True)
 s.path([(392,980),(428,980)])
 s.path([(600,1060),(600,1130)])
 s.path([(392,1210),(428,1210)],both=True)
 s.path([(772,1210),(808,1210)],'review',both=True)
 s.path([(600,1290),(600,1332),(980,1332),(980,1370)])
 s.path([(808,1450),(772,1450)])
 s.path([(428,1450),(392,1450)])
 s.path([(600,1290),(600,1310),(24,1310),(24,1670),(48,1670)],'observe',dash=True)
 s.path([(600,1530),(600,1600)],'observe',dash=True)
 s.path([(220,1530),(220,1550),(980,1550),(980,1600)],'review')

 s.card(48,210,6,'CISO Assistant',['Risk register • controls • evidence','Accountable ownership','Human-held risk acceptance'],PURPLE)
 s.card(428,210,13,'GLPI',['Service / entity inventory','Change and remediation records','Ticket-based follow-through'],PURPLE)
 s.card(808,210,7,'OpenMetadata',['Data ownership and classification','Source context and lineage','Governed metadata references'],PURPLE)
 s.card(48,440,15,'Fairlearn',['Group-performance metrics','Synthetic evaluation fixture','Evidence feeds model validation'],PURPLE)
 s.card(428,440,8,'MLflow',['Evaluation and artifact versions','Candidate / validated aliases','Approval evidence and expiry'],PURPLE)
 s.card(808,440,17,'Syft · Grype · Cosign',['Built-image SBOM','Vulnerability release gate','Verified offline artifact signature'],PURPLE)
 s.card(48,670,1,'Keycloak',['Signed JWT identity','Issuer, audience and lifetime','Explicit principal mapping'])
 s.card(428,670,4,'OpenFGA',['Assigned-case relationships','Record-scope authorization','Deny unauthorized relationships'])
 s.card(808,670,9,'OpenBao',['Separate runtime secret paths','Gateway / worker / dispatcher','Scoped credentials and custody'])
 s.card(48,900,16,'Kubernetes + Cilium',['Isolated non-root agent workload','Explicit gateway / identity egress','No direct target credentials'])
 s.card(428,900,2,'Microsoft AGT',['Agent Governance Toolkit','Deterministic tool interception','Local allow cannot override deny'])
 s.card(808,900,3,'OPA',['Business-policy allow / deny','Context, limits and validation','Mandatory execution restrictions'])
 s.card(48,1130,18,'Ollama + Qwen2.5',['Local JSON proposal generation','Bounded intent is revalidated','No execution credentials'])
 s.card(428,1130,None,'Execution gateway',['Verify identity and trusted facts','Recheck policy and exact action','Enforce the only write route'],own=True)
 s.card(808,1130,5,'Temporal',['Durable workflow execution','Human approval-reference wait','Bounded activity retries'],ORANGE)
 s.card(48,1370,None,'Evidence delivery',['Per-sink outbox and receipts','Risk / control / evidence links','Correlated incidents and tickets'],own=True)
 s.card(428,1370,14,'PostgreSQL',['Business state + audit + outbox','Shared budget and idempotency','Atomic local transaction'])
 s.card(808,1370,None,'Exclusive target adapter',['Typed business-system operation','Explicit execution boundary','No unrestricted agent write API'],own=True)
 s.card(48,1600,10,'OpenTelemetry',['Minimized execution spans','OTLP export to collector','Correlated operational evidence'],ORANGE)
 s.card(428,1600,11,'Prometheus + Alertmanager',['Decision / backlog metrics','Rules and authenticated alerts','Alerts enter the incident path'],ORANGE)
 s.card(808,1600,12,'DFIR-IRIS',['Customer-scoped native alerts','Investigation and containment','Recovery and evidence tracking'],ORANGE)
 s.path([(52,1800),(122,1800)]);s.text(138,1806,'Execution / commitment',16)
 s.path([(440,1800),(510,1800)],'context',dash=True);s.text(526,1806,'Authority / release context',16)
 s.path([(848,1800),(918,1800)],'observe',dash=True);s.text(934,1806,'Operational signals',16)
 s.text(48,1842,'Feedback: incidents inform risk and control review (#06), remediation (#13) and revalidation (#08).',16,MUTED)
 s.text(48,1867,'Reference implementation map. Complete native deployment remains subject to live acceptance.',14,MUTED)
 assert s.seen==set(range(1,19)),s.seen
 return s.save('system-architecture-18.svg')

def lifecycle():
 s=SVG(1200,820,'From proposal to an authorized effect','Six stages show how the implementation authenticates a proposal, obtains trusted context, evaluates business policy, checks required approval, commits the target and records operational evidence.')
 s.rect(0,0,1200,124,INK,radius=16)
 s.text(48,48,'EXECUTION & GOVERNANCE LIFECYCLE',16,'#8dd8d6',700)
 s.text(48,94,'From proposal to an authorized effect',32,'#ffffff',700)
 specs=[(48,182,'1  Authenticate & intercept',['Keycloak (#01) verifies identity.','Microsoft AGT (#02) checks tools.','The agent cannot nominate its role.']),
 (428,182,'2  Resolve trusted context',['OpenFGA (#04): record scope.','Metadata / release / inventory:','OpenMetadata, MLflow, GLPI.']),
 (808,182,'3  Evaluate business policy',['OPA (#03) applies current limits.','Unknown or invalid authority denies.','A model proposal is not permission.']),
 (808,464,'4  Check required approval',['Temporal (#05) waits durably.','Gateway binds the exact action,','versions, reviewer and expiry.']),
 (428,464,'5  Commit at the boundary',['Exclusive adapter commits once.','PostgreSQL (#14) stores the action,','approval use, audit and outbox.']),
 (48,464,'6  Observe & respond',['OTel (#10) and monitoring (#11).','IRIS (#12), CISO (#06) and GLPI','receive linked operational evidence.'])]
 for x,y,title,lines in specs:s.card(x,y,None,title,lines,own=True,w=344,h=192)
 for a,b in [((392,278),(428,278)),((772,278),(808,278)),((980,374),(980,464)),((808,560),(772,560)),((428,560),(392,560))]:s.path([a,b])
 s.rect(48,706,1104,74,'#eef7f7')
 s.text(68,734,'Approval never overrides a hard denial. Retries reuse a scoped idempotency key.',18,TEAL,700)
 s.text(68,762,'Model generation, isolation, secret custody, evaluation and release assurance support this path.',17,MUTED)
 return s.save('execution-governance-flow.svg')
if __name__=='__main__':
 for p in [architecture(),lifecycle()]:print(p)
