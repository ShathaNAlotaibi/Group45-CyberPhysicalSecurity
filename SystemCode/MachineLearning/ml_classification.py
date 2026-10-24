import json, shutil
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
try:
    from IPython.display import display
except ImportError:
    def display(value): print(value)
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier, plot_tree, export_text
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
import joblib
OUTPUT = Path('results')
OUTPUT.mkdir(exist_ok=True)
RANDOM_STATE = 42
TEST_SIZE = 0.20

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold
OUTPUT = Path('results')
OUTPUT.mkdir(exist_ok=True)

BLUE_COLORS = {'Decision Tree':'#9CC9E8','Random Forest':'#3B82B8','Gradient Boosting':'#123E68'}
plt.rcParams['axes.prop_cycle'] = plt.cycler(color=list(BLUE_COLORS.values()))


# Load both supplied files. No Drive mount is needed.
def obtain_file(expected, suffix):
    path = Path(expected)
    if path.exists(): return path
    from google.colab import files
    print('Upload:', expected)
    uploaded = files.upload()
    if expected in uploaded: return Path(expected)
    matches = [name for name in uploaded if name.lower().endswith(suffix)]
    if len(matches) != 1: raise ValueError('Upload exactly the requested file.')
    return Path(matches[0])
RAW_PATH = obtain_file('RawDataset(2).xlsx', '.xlsx')
MERGED_PATH = obtain_file('Merged Dataset.csv', '.csv')


sheets = pd.read_excel(RAW_PATH, sheet_name=None)
required = {'Users': ['user_id','device_id','normal_start','normal_end'],
            'Physical Events': ['event_id','user_id','timestamp','location_type','access_result'],
            'Cyber Events': ['event_id','user_id','device_id','timestamp','failed_logins','files_accessed','sensitive_files','usb_connected']}
clean = {}
for name, columns in required.items():
    if name not in sheets:
        raise ValueError(f'Missing sheet: {name}')
    frame = sheets[name].copy()
    frame.columns = frame.columns.astype(str).str.strip()
    if not set(columns).issubset(frame.columns):
        raise ValueError(f'{name}: missing columns {set(columns) - set(frame.columns)}')
    for col in frame.select_dtypes(include=['object','string']).columns:
        frame[col] = frame[col].map(lambda value: value.strip() if isinstance(value, str) else value)
        frame[col] = frame[col].replace('', np.nan)
    before = len(frame)
    frame = frame.drop_duplicates().reset_index(drop=True)
    print(name, 'shape:', frame.shape, 'exact duplicates removed:', before-len(frame))
    display(frame.isna().sum().to_frame('Missing'))
    clean[name] = frame
users, physical, cyber = [clean[name] for name in required]
for frame, key in [(users,'user_id'), (physical,'event_id'), (cyber,'event_id')]:
    if frame[key].isna().any() or frame[key].duplicated().any():
        raise ValueError(f'Missing or conflicting duplicate {key}')
for frame in [physical, cyber]:
    frame['timestamp'] = pd.to_datetime(frame['timestamp'], errors='coerce')
    if frame[['timestamp','user_id']].isna().any().any():
        raise ValueError('Event timestamp/user ID missing or invalid; review before matching.')

physical['pair_number'] = pd.to_numeric(physical['event_id'].str.extract(r'^P(\d+)$')[0], errors='raise')
cyber['pair_number'] = pd.to_numeric(cyber['event_id'].str.extract(r'^C(\d+)$')[0], errors='raise')
if physical['pair_number'].isna().any() or cyber['pair_number'].isna().any():
    raise ValueError('Unexpected event ID format.')
if set(physical['pair_number']) != set(cyber['pair_number']):
    raise ValueError('Unmatched event pairs; review raw data.')
physical = physical.rename(columns={'event_id':'event_id_physical','timestamp':'physical_timestamp'})
cyber = cyber.rename(columns={'event_id':'event_id_cyber','timestamp':'cyber_timestamp','device_id':'cyber_device_id','user_id':'cyber_user_id'})
df = physical.merge(cyber, on='pair_number', validate='one_to_one')
if not df['user_id'].eq(df['cyber_user_id']).all():
    raise ValueError('Paired events belong to different users.')
users = users.rename(columns={'device_id':'assigned_device_id'})
df = df.merge(users, on='user_id', how='left', validate='many_to_one', indicator=True)
if not df['_merge'].eq('both').all():
    raise ValueError('Some event users are absent from Users.')
if not df['cyber_device_id'].eq(df['assigned_device_id']).all():
    raise ValueError('Device assignment mismatch; review before modeling.')
df = df.drop(columns='_merge')
print('Merged raw scenarios:', len(df))

raw_join = df.copy()


# Use the merged file as the authoritative source, with one label per scenario.
df = pd.read_csv(MERGED_PATH)
df.columns = df.columns.str.strip()
for col in df.select_dtypes(include=['object','string']).columns:
    df[col] = df[col].map(lambda v: v.strip() if isinstance(v,str) else v).replace('',np.nan)
keys = ['event_id_physical','event_id_cyber','user_id','physical_timestamp','cyber_timestamp']
required = keys + ['risk_level','normal_start','normal_end','location_type','access_result',
                   'failed_logins','files_accessed','sensitive_files','usb_connected']
if not set(required).issubset(df.columns): raise ValueError('Merged file missing required columns.')
for col in ['physical_timestamp','cyber_timestamp']:
    df[col] = pd.to_datetime(df[col],errors='coerce')
if df[keys+['risk_level']].isna().any().any(): raise ValueError('Invalid identifiers, timestamps or labels.')
if df.duplicated(keys).any(): raise ValueError('Duplicate scenario key in merged file.')
if not set(df['risk_level']) == {'Low','Medium','High'}: raise ValueError('Expected Low, Medium and High labels.')
# Validate all shared raw attributes against the original workbook.
compare_cols = ['location','location_type','access_result','failed_logins','files_accessed',
                'sensitive_files','usb_connected','role','department','normal_start','normal_end']
compare_cols = [c for c in compare_cols if c in df and c in raw_join]
check = df[keys+compare_cols].merge(raw_join[keys+compare_cols],on=keys,how='outer',
                                 suffixes=('_merged','_raw'),validate='one_to_one',indicator=True)
if not check['_merge'].eq('both').all(): raise ValueError('Raw and merged scenario keys differ.')
for col in compare_cols:
    if not check[col+'_merged'].fillna('<missing>').eq(check[col+'_raw'].fillna('<missing>')).all():
        raise ValueError(f'Raw/merged mismatch: {col}')
for merged_device in ['device_id_x','device_id_y']:
    if merged_device in df:
        device_check = df[keys+[merged_device]].merge(raw_join[keys+['cyber_device_id']],on=keys,validate='one_to_one')
        if not device_check[merged_device].eq(device_check['cyber_device_id']).all(): raise ValueError('Device mismatch.')
label_reference = df[keys+['risk_level']].copy()
label_reference.to_csv('Risk_Labels.csv',index=False)
print('Verified raw/merged matches:',len(df))
display(df['risk_level'].value_counts())



def clock_minutes(series):
    parsed = pd.to_datetime(series.astype(str), format='%H:%M', errors='coerce')
    if parsed.isna().any():
        raise ValueError('Invalid working hours; expected HH:MM.')
    return parsed.dt.hour * 60 + parsed.dt.minute
start, end = clock_minutes(df['normal_start']), clock_minutes(df['normal_end'])
for domain in ['physical','cyber']:
    timestamp = df[f'{domain}_timestamp']
    minute = timestamp.dt.hour * 60 + timestamp.dt.minute
    within = np.where(start <= end, (minute >= start) & (minute <= end), (minute >= start) | (minute <= end))
    df[f'{domain}_after_hours'] = (~within).astype(int)
    df[f'{domain}_hour'] = timestamp.dt.hour
    df[f'{domain}_is_weekend'] = (timestamp.dt.dayofweek >= 5).astype(int)

for col, choices in [('location_type', {'normal':'Normal','restricted':'Restricted'}),
                     ('access_result', {'granted':'Granted','denied':'Denied'})]:
    normalized = df[col].astype('string').str.lower()
    if (normalized.notna() & ~normalized.isin(choices)).any():
        raise ValueError(f'Unexpected values in {col}')
    df[col] = normalized.map(choices)
df['restricted_location'] = df['location_type'].map({'Normal':0,'Restricted':1})
df['access_denied'] = df['access_result'].map({'Granted':0,'Denied':1})
df['time_gap_minutes'] = (df['cyber_timestamp']-df['physical_timestamp']).dt.total_seconds()/60
if (df['time_gap_minutes'] < 0).any():
    raise ValueError('Cyber event precedes its paired physical event; review pairing.')
for col in ['failed_logins','files_accessed','sensitive_files','usb_connected']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
    if (df[col].dropna() < 0).any():
        raise ValueError(f'Negative count in {col}')
if not df['usb_connected'].dropna().isin([0,1]).all():
    raise ValueError('usb_connected must contain 0/1.')
cyber_features = ['failed_logins','files_accessed','sensitive_files','usb_connected','cyber_after_hours','cyber_hour','cyber_is_weekend']
physical_features = ['restricted_location','access_denied','physical_after_hours','physical_hour','physical_is_weekend']

feature_sets = {'Cyber-only':cyber_features, 'Physical-only':physical_features,
                'Hybrid':cyber_features+physical_features+['time_gap_minutes']}
for name, features in feature_sets.items():
    print(name, features)
model_data = df[feature_sets['Hybrid']+['risk_level']].copy()
model_data.to_csv(OUTPUT/'preprocessed_raw_dataset.csv', index=False)
display(model_data.head())

df.to_csv(OUTPUT/'merged_preprocessed_audit.csv',index=False)
for name,frame in clean.items():
    frame.to_csv(OUTPUT/(name.lower().replace(' ','_')+'_cleaned.csv'),index=False)
pd.DataFrame([{'Sheet':name,'Raw_rows':len(sheets[name]),'Clean_rows':len(frame),
               'Exact_duplicates_removed':len(sheets[name])-len(frame),'Missing_cells':int(frame.isna().sum().sum())}
              for name,frame in clean.items()]).to_csv(OUTPUT/'preprocessing_audit.csv',index=False)
model_data.isna().sum().rename('Missing').to_csv(OUTPUT/'feature_missing_values.csv')

# Export the exact predictor sets with shared target and traceability IDs.
for name,columns in feature_sets.items():
    subset = df[['event_id_physical','event_id_cyber','user_id']+columns+['risk_level']].copy()
    subset.to_csv(OUTPUT/(name.lower().replace('-','_')+'_features.csv'),index=False)


# One shared split; no tuning on test data. Repeated users may occur in both sets:
# this evaluates new scenarios in this synthetic population, not unseen users.
y = df['risk_level'].astype(str)
classes = ['Low', 'Medium', 'High']
if set(classes) != set(y.unique()):
    raise ValueError('Unexpected risk labels.')
train_idx, test_idx = train_test_split(df.index, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y)
pd.DataFrame({'row_index':df.index,'split':np.where(df.index.isin(train_idx),'train','test')}).to_csv(OUTPUT/'split_assignments.csv',index=False)
print('Train:', len(train_idx), 'Test:', len(test_idx))
print('Users appearing in both:', len(set(df.loc[train_idx,'user_id']) & set(df.loc[test_idx,'user_id'])))
results, metrics = {}, []
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
model_specs = {
 'Decision Tree': (DecisionTreeClassifier(random_state=RANDOM_STATE),
     {'classifier__max_depth':[3,5,None], 'classifier__min_samples_leaf':[1,5], 'classifier__class_weight':[None,'balanced']}),
 'Random Forest': (RandomForestClassifier(n_estimators=150,random_state=RANDOM_STATE,n_jobs=1),
     {'classifier__max_depth':[5,None], 'classifier__min_samples_leaf':[1,3], 'classifier__max_features':['sqrt',1.0], 'classifier__class_weight':[None,'balanced']}),
 'Gradient Boosting': (GradientBoostingClassifier(random_state=RANDOM_STATE),
     {'classifier__n_estimators':[100,200], 'classifier__learning_rate':[0.05,0.1], 'classifier__max_depth':[2,3]})
}
experiments = [(domain, model_name, features, estimator, grid)
               for domain, features in feature_sets.items()
               for model_name, (estimator, grid) in model_specs.items()]
for domain, model_name, features, estimator, grid in experiments:
    name = f'{domain} / {model_name}'
    X_train, X_test = df.loc[train_idx,features], df.loc[test_idx,features]
    numeric = X_train.select_dtypes(include='number').columns.tolist()
    categorical = [col for col in features if col not in numeric]
    transforms = []
    if numeric:
        transforms.append(('num',SimpleImputer(strategy='median',keep_empty_features=True),numeric))
    if categorical:
        transforms.append(('cat',Pipeline([('imputer',SimpleImputer(strategy='most_frequent',keep_empty_features=True)),
                                           ('encoder',OneHotEncoder(handle_unknown='ignore',sparse_output=False))]),categorical))
    pipeline = Pipeline([('preprocessor',ColumnTransformer(transforms)),
                         ('classifier',estimator)])
    search = GridSearchCV(pipeline, grid, scoring={'macro_f1':'f1_macro','accuracy':'accuracy'},
                          refit='macro_f1', cv=cv, n_jobs=2, return_train_score=False)
    search.fit(X_train, y.loc[train_idx])
    pipeline = search.best_estimator_
    pd.DataFrame(search.cv_results_).to_csv(OUTPUT/f"{domain}_{model_name}_cv_results.csv",index=False)
    print(name, 'best parameters:',search.best_params_, 'CV macro F1:',search.best_score_,flush=True)
    predicted = pipeline.predict(X_test)
    actual = y.loc[test_idx]
    report = classification_report(actual,predicted,labels=classes,output_dict=True,zero_division=0)
    row = {'Model':name,'Domain':domain,'Classifier':model_name,'CV Macro F1':search.best_score_,'CV Accuracy':search.cv_results_['mean_test_accuracy'][search.best_index_],'Accuracy':accuracy_score(actual,predicted)}
    for average in ['macro','weighted']:
        for metric, function in [('Precision',precision_score),('Recall',recall_score),('F1',f1_score)]:
            row[f'{metric} ({average})'] = function(actual,predicted,labels=classes,average=average,zero_division=0)
    row['High-risk Recall'] = report.get('High',{}).get('recall',np.nan)
    metrics.append(row)
    slug = name.lower().replace('-','_').replace(' / ','_').replace(' ','_')
    print('\n',name)
    print(classification_report(actual,predicted,labels=classes,zero_division=0))
    pd.DataFrame(report).T.to_csv(OUTPUT/f'{slug}_classification_report.csv')
    cm = confusion_matrix(actual,predicted,labels=classes)
    pd.DataFrame(cm,index=classes,columns=classes).to_csv(OUTPUT/f'{slug}_confusion_matrix.csv')
    fig, ax = plt.subplots(figsize=(6,5))
    ConfusionMatrixDisplay(cm,display_labels=classes).plot(ax=ax,cmap='Blues',colorbar=False)
    ax.set_title(f'{name}: confusion matrix')
    fig.tight_layout(); fig.savefig(OUTPUT/f'{slug}_confusion_matrix.png',dpi=160); plt.show(); plt.close()
    names = pipeline.named_steps['preprocessor'].get_feature_names_out()
    importance = pd.DataFrame({'Feature':names,'Importance':pipeline.named_steps['classifier'].feature_importances_}).sort_values('Importance',ascending=False)
    importance.to_csv(OUTPUT/f'{slug}_feature_importance.csv',index=False)
    display(importance)
    fig, ax = plt.subplots(figsize=(9,5))
    importance.head(15).iloc[::-1].plot.barh(x='Feature',y='Importance',ax=ax,legend=False)
    ax.set_title(f'{name}: feature importance'); fig.tight_layout()
    fig.savefig(OUTPUT/f'{slug}_feature_importance.png',dpi=160); plt.show(); plt.close()
    predictions = df.loc[test_idx,['event_id_physical','event_id_cyber','user_id']+features].copy()
    predictions['Actual_Risk'], predictions['Predicted_Risk'] = actual, predicted
    errors = predictions[predictions['Actual_Risk'] != predictions['Predicted_Risk']]
    predictions.to_csv(OUTPUT/f'{slug}_predictions.csv',index=False)
    errors.to_csv(OUTPUT/f'{slug}_misclassified.csv',index=False)
    joblib.dump(pipeline,OUTPUT/f'{slug}_model.joblib')
    results[name] = {'pipeline':pipeline,'errors':errors,'features':names,'best_params':search.best_params_}
comparison = pd.DataFrame(metrics).set_index('Model')
comparison.to_csv(OUTPUT/'model_comparison.csv')
display(comparison.round(4))
print('Recommended hybrid model selected by training CV:', comparison[comparison['Domain']=='Hybrid']['CV Macro F1'].idxmax())


# Final test comparison; parameter/model selection uses training CV only.
score_columns = ['Accuracy','Precision (macro)','Recall (macro)','F1 (macro)','High-risk Recall']
for metric in ['Accuracy','F1 (macro)','High-risk Recall']:
    table = comparison.pivot(index='Domain',columns='Classifier',values=metric).reindex(['Cyber-only','Physical-only','Hybrid'])
    ax = table.plot.bar(figsize=(10,5),rot=0,ylim=(0,1))
    ax.set_title(f'Test {metric}'); ax.set_ylabel('Score'); ax.figure.tight_layout()
    ax.figure.savefig(OUTPUT/f"comparison_{metric.replace(' ','_')}.png",dpi=160); plt.show(); plt.close()
selected_name = comparison[comparison['Domain']=='Hybrid']['CV Macro F1'].idxmax()
print('Recommended hybrid model, selected using CV macro F1:',selected_name)
for name, result in results.items():
    errors = result['errors']
    summary = errors.groupby(['Actual_Risk','Predicted_Risk']).size().reset_index(name='Count')
    summary.to_csv(OUTPUT/(name.replace(' / ','_').replace(' ','_')+'_error_summary.csv'),index=False)
    print(name, ':',len(errors),'errors of',len(test_idx)); display(summary)
display(results[selected_name]['errors'])
# Preserve settings and evidence for reproducibility.
settings = {name:result['best_params'] for name,result in results.items()}
(OUTPUT/'best_parameters.json').write_text(json.dumps(settings,indent=2))
(OUTPUT/'methodology.txt').write_text(
    'Labels: existing MergedDataset.csv lookup; raw workbook contains no risk labels.\n'
    '80/20 stratified split, random_state=42; same rows for nine experiments.\n'
    '5-fold stratified CV inside training only; parameters and recommended hybrid selected by macro F1.\n'
    'All preprocessing learned inside pipeline/CV. Score, severity and identifiers excluded.\n'
    'Test results exploratory: test set was previously examined; users overlap across splits.\n'
    'Feature importance is model-specific, not causal. Synthetic label agreement is not real-world validation.\n')


# Explain the tuned hybrid Decision Tree even if an ensemble wins.
hybrid = results['Hybrid / Decision Tree']
text_rules = export_text(hybrid['pipeline'].named_steps['classifier'],feature_names=list(hybrid['features']))
(OUTPUT/'hybrid_decision_tree_rules.txt').write_text(text_rules)
print(text_rules)
fig, ax = plt.subplots(figsize=(30,16))
plot_tree(hybrid['pipeline'].named_steps['classifier'],feature_names=hybrid['features'],
          class_names=hybrid['pipeline'].named_steps['classifier'].classes_,filled=False,max_depth=None,fontsize=8,ax=ax)
ax.set_title('Hybrid Decision Tree: full trained tree')
fig.tight_layout(); fig.savefig(OUTPUT/'hybrid_decision_tree.png',dpi=160); plt.show(); plt.close()


from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.ticker import PercentFormatter
from sklearn.metrics import ConfusionMatrixDisplay
from sklearn.tree import plot_tree
import joblib
OUTPUT = Path('results')
BLUE_COLORS = {'Decision Tree':'#9CC9E8','Random Forest':'#3B82B8','Gradient Boosting':'#123E68'}
plt.rcParams.update({'axes.prop_cycle':plt.cycler(color=list(BLUE_COLORS.values())),
 'font.size':11,'axes.titleweight':'bold','axes.spines.top':False,'axes.spines.right':False,
 'axes.labelcolor':'#17344F','text.color':'#17344F','figure.facecolor':'white','savefig.facecolor':'white'})
comparison=pd.read_csv(OUTPUT/'model_comparison.csv')
models=list(BLUE_COLORS);domains=['Cyber-only','Physical-only','Hybrid']
slug=lambda d,m:(d+' '+m).lower().replace('-','_').replace(' ','_')
def save(fig,path):
 fig.tight_layout();fig.savefig(path,dpi=200,bbox_inches='tight')
 if Path(path).name in ['metrics_comparison.png','confusion_matrices.png'] or Path(path).name.startswith('comparison_'): plt.show()
 plt.close(fig)
for metric in ['Accuracy','F1 (macro)','High-risk Recall']:
 table=comparison.pivot(index='Domain',columns='Classifier',values=metric).reindex(index=domains,columns=models)
 ax=table.plot.bar(figsize=(10,5),rot=0,color=list(BLUE_COLORS.values()),width=.72)
 ax.set_ylim(0,1.10);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_ylabel(metric);ax.set_xlabel('Feature set');ax.set_title('Cyber, physical and hybrid: '+metric)
 ax.legend(title='Classifier',loc='upper left',bbox_to_anchor=(1.01,1),frameon=False)
 for container in ax.containers:ax.bar_label(container,labels=[f'{v.get_height():.1%}' for v in container],fontsize=9,padding=3)
 save(ax.figure,OUTPUT/f"comparison_{metric.replace(' ','_')}.png")
for domain in domains:
 group=OUTPUT/'grouped_figures'/domain.lower().replace('-','_');group.mkdir(parents=True,exist_ok=True)
 subset=comparison[comparison.Domain==domain].set_index('Classifier').reindex(models)
 metrics=['Accuracy','Precision (macro)','Recall (macro)','F1 (macro)','High-risk Recall']
 fig,ax=plt.subplots(figsize=(11,5.5));x=np.arange(len(metrics));width=.24
 for j,model in enumerate(models):
  bars=ax.bar(x+(j-1)*width,subset.loc[model,metrics].astype(float),width,label=model,color=BLUE_COLORS[model])
  ax.bar_label(bars,labels=[f'{b.get_height():.0%}' for b in bars],fontsize=8,padding=3)
 ax.set_xticks(x,[m.replace(' (macro)','\n(macro)').replace('High-risk Recall','High-risk\nrecall') for m in metrics]);ax.set_ylim(0,1.12);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_ylabel('Test score');ax.set_title(domain+' feature set | three classifiers');ax.legend(loc='upper left',bbox_to_anchor=(1.01,1),frameon=False)
 save(fig,group/'metrics_comparison.png')
 fig,axes=plt.subplots(1,3,figsize=(13,4));cms=[]
 for model in models:cms.append(pd.read_csv(OUTPUT/f'{slug(domain,model)}_confusion_matrix.csv',index_col=0))
 vmax=max(a.values.max() for a in cms)
 for ax,model,cm in zip(axes,models,cms):
  ConfusionMatrixDisplay(cm.values,display_labels=cm.index).plot(ax=ax,cmap='Blues',colorbar=False,im_kw={'vmin':0,'vmax':vmax})
  ax.set_title(model)
 fig.suptitle(domain+' | confusion matrices (same count scale)',fontsize=14,fontweight='bold');save(fig,group/'confusion_matrices.png')
 for model in models:
  s=slug(domain,model);cm=pd.read_csv(OUTPUT/f'{s}_confusion_matrix.csv',index_col=0)
  fig,ax=plt.subplots(figsize=(6,5));ConfusionMatrixDisplay(cm.values,display_labels=cm.index).plot(ax=ax,cmap='Blues',colorbar=False);ax.set_title(domain+' / '+model);save(fig,OUTPUT/f'{s}_confusion_matrix.png')
  imp=pd.read_csv(OUTPUT/f'{s}_feature_importance.csv').head(12).iloc[::-1];fig,ax=plt.subplots(figsize=(9,5))
  ax.barh(imp.Feature.str.removeprefix('num__'),imp.Importance,color=BLUE_COLORS[model]);ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('Impurity-based importance');ax.set_title(domain+' / '+model);save(fig,OUTPUT/f'{s}_feature_importance.png')
  if model=='Decision Tree':
   pipeline=joblib.load(OUTPUT/f'{s}_model.joblib');tree=pipeline.named_steps['classifier'];names=pipeline.named_steps['preprocessor'].get_feature_names_out()
   fig,ax=plt.subplots(figsize=(30,16));nodes=plot_tree(tree,feature_names=names,class_names=tree.classes_,filled=True,max_depth=None,fontsize=9,ax=ax)
   impurity=tree.tree_.impurity;maximp=max(float(impurity.max()),1e-9)
   for node,imp in zip([n for n in nodes if n.get_bbox_patch() is not None],impurity):
    node.get_bbox_patch().set_facecolor(plt.cm.Blues(.12+.48*(1-float(imp)/maximp)))
    node.get_bbox_patch().set_edgecolor('#17344F');node.set_color('#102C43')
   ax.set_title(domain+' | full Decision Tree; darker blue = purer node');save(fig,group/'decision_tree_full.png')
   if domain=='Hybrid':
    import shutil
    shutil.copy2(group/'decision_tree_full.png',OUTPUT/'hybrid_decision_tree.png')
print('Blue figures generated for all nine experiments.')


# Download preprocessing, metrics, plots, models and errors as one ZIP.
archive = shutil.make_archive('RawDataset_MultiModel_Results','zip',OUTPUT)
print('Saved:',archive)
try:
    from google.colab import files
    files.download(archive)
except ImportError:
    print('Outside Colab: find the ZIP in the working directory.')
