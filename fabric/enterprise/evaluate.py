"""Real Fairlearn metrics over explicitly synthetic data; publish candidate to MLflow."""
import json
from pathlib import Path
from fairlearn.metrics import MetricFrame,selection_rate
from sklearn.metrics import accuracy_score
from .clients import MLflowRegistry

def evaluate():
 y=[1,0,1,0,1,0,1,0];pred=[1,0,1,0,1,0,1,0];groups=['a']*4+['b']*4
 frame=MetricFrame(metrics={'approval_rate':selection_rate,'accuracy':accuracy_score},y_true=y,y_pred=pred,sensitive_features=groups)
 metrics={'fairness_difference':float(frame.difference()['approval_rate']),'accuracy':float(frame.overall['accuracy'])}
 artifact={'dataset':'synthetic-eight-record-fixture','group_metrics':frame.by_group.to_dict(),
           'limitations':'This fixture tests metric plumbing, not fair lending validity or independent validation.'}
 receipt=MLflowRegistry().publish_evaluation(metrics,artifact)
 return {'metrics':metrics,'receipt':receipt,'release':'candidate only; an independent validator must promote'}
if __name__=='__main__':print(json.dumps(evaluate(),indent=2))
