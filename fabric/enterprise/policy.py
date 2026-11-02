"""Deny wins. Trusted service results never come from agent body."""
from fabric.core import OPA,VERSION
from .clients import OpenFGA,OpenMetadata,MLflowRegistry,GLPI,DependencyFailure,required
class EnterprisePolicy:
 def __init__(self,opa_url):self.opa=OPA(opa_url)
 def decide(self,ctx):
  # Cheap hard restrictions first, then authoritative external checks.
  local=self.opa.decide(ctx)
  if not local['allow']:return local
  if ctx['principal']['tenant']!=required('MODEL_TENANT'):
   return {'allow':False,'reasons':['model_tenant_not_validated'],'version':VERSION}
  fga=OpenFGA();metadata=OpenMetadata();glpi=None
  try:
   if not fga.check(ctx['principal']['id'],ctx['case']['id']):
    return {'allow':False,'reasons':['relationship_denied'],'version':VERSION}
   metadata.assert_classified();MLflowRegistry().validate()
   glpi=GLPI();service=glpi.service()
   if service.get('is_deleted') or not service.get('id'):raise DependencyFailure('Service inventory invalid')
   return local
  finally:
   fga.close();metadata.close()
   if glpi:glpi.close()
