"""Small in-process counters; deployments can scrape them through the admin endpoint later."""
from collections import Counter
metrics=Counter()
def inc(name):metrics[name]+=1
def snapshot():return dict(metrics)
