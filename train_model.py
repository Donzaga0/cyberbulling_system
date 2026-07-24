import os, re, joblib, pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion
from sklearn.metrics import classification_report, accuracy_score

samples = {
'normal': [
'good morning everyone','thank you for your support','please send the document today','happy birthday my friend','the meeting starts at ten','I enjoyed your presentation','let us work together','welcome to the group','your idea is very helpful','have a wonderful day','can we discuss the assignment','congratulations on your success','I agree with your opinion','please take care of yourself','see you tomorrow','the weather is nice today','I appreciate your effort','let us solve the problem calmly','your work looks excellent','kindly check your email'],
'offensive_words': [
'you are an idiot','what a stupid person','you are a fool','shut up moron','this is damn nonsense','you are so dumb','get lost you loser','you are useless','what an ugly fool','you talk rubbish','you are pathetic','stupid idiot','your brain is empty','you are a complete clown','nonsense human being','you are very foolish','go away dummy','you are a disgrace','silly useless person','you sound like an idiot'],
'toxic_language': [
'everything you say is disgusting','nobody wants your negative energy here','you ruin every conversation','your presence makes this place worse','you are always causing problems','people are tired of your behaviour','you make everyone uncomfortable','your comments are completely toxic','you bring nothing but trouble','stop spreading your poison','you are unbearable to work with','all your ideas are terrible','you never do anything right','everyone is better without you','your attitude is disgusting','you destroy every good discussion','you are the worst person here','nothing good comes from you','you make this group miserable','your words are full of bitterness'],
'harassment': [
'I will keep messaging until you answer me','you cannot hide from me online','I am watching everything you post','reply now or I will continue disturbing you','I will follow you everywhere','stop ignoring me I will not leave you alone','I will contact all your friends about you','you must talk to me whether you like it or not','I will keep calling your phone','I know where you spend your time','I will embarrass you every day','you cannot block me forever','I will continue sending messages all night','answer me now you have no choice','I will post about you repeatedly','I am going to monitor your account','I will keep creating accounts to reach you','you will hear from me every single day','I refuse to leave you alone','I will continue bothering you'],
'cyberbullying': [
'everyone should laugh at your embarrassing photo','we created a group to make fun of you','I will post your mistake so the whole school can mock you','nobody online likes you','leave this group because nobody wants you','we will keep sharing memes about you','everyone should block this loser','let us expose and shame this person','your classmates are laughing at you online','I will spread rumours about you on social media','we made a fake account to mock you','everyone repost this embarrassing picture','you do not belong in this online community','we will humiliate you in the group chat','I will tag everyone so they can insult you','the whole class thinks you are a joke','we will keep making fun of your posts','your video deserves public ridicule','I will upload your private photo to shame you','everyone in the chat hates you'],
'hate_speech': [
'people of your religion are all evil','your ethnic group does not belong here','women are inferior and should stay silent','all people from your tribe are criminals','your race is disgusting','people like you should be removed because of your identity','I hate everyone from your country','your religion makes you worthless','that ethnic community is a disease','men from that group are animals','people with your disability are useless','your gender should not have any rights','all immigrants are dirty criminals','your tribe should be banned','your race is not welcome here','people of that faith are dangerous','your identity makes you less human','everyone from your community is stupid','your people should leave this country','I hate your entire ethnic group'],
'threats': [
'I will hurt you','I am going to beat you','you will pay for this tonight','I will find you and attack you','I will destroy your life','I am coming to harm you','watch your back because I will get you','I will break your face','I will deal with you violently','you are going to regret this','I know where you live and I will come for you','I will make you suffer','I will attack you after school','I am going to kill you','I will burn your property','you will not be safe when I see you','I will punish you physically','I am bringing people to beat you','I will destroy everything you own','this is your last warning before I hurt you']}
rows=[{'text':t,'label':label} for label,texts in samples.items() for t in texts]
df=pd.DataFrame(rows)
df.to_csv('dataset/multiclass_harmful_messages.csv',index=False)
X_train,X_test,y_train,y_test=train_test_split(df.text,df.label,test_size=.25,random_state=42,stratify=df.label)
vectorizer=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,min_df=1,max_features=12000)
Xtr=vectorizer.fit_transform(X_train); Xte=vectorizer.transform(X_test)
model=LogisticRegression(max_iter=2000,class_weight='balanced',C=4.0)
model.fit(Xtr,y_train)
pred=model.predict(Xte)
print('Accuracy:',round(accuracy_score(y_test,pred),4))
print(classification_report(y_test,pred,zero_division=0))
os.makedirs('model',exist_ok=True)
joblib.dump(model,'model/bullying_model.pkl'); joblib.dump(vectorizer,'model/vectorizer.pkl')
