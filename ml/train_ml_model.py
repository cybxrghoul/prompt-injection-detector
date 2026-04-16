import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os

data_path = "../data/detection_logs.csv"
df = pd.read_csv(data_path)

X = df['prompt'].astype(str)
y = df['blocked'].astype(str).str.lower().map(lambda b: b == 'true').astype(int)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.18, random_state=42, stratify=y)

vectorizer = TfidfVectorizer(ngram_range=(1,2), max_features=2500, lowercase=True)
X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)

clf = LogisticRegression(max_iter=800, class_weight='balanced')

clf.fit(X_train_tfidf, y_train)

print("Model training complete.")

preds = clf.predict(X_test_tfidf)
print(classification_report(y_test, preds))

os.makedirs("ml", exist_ok=True)
joblib.dump(vectorizer, "ml/vectorizer.pkl")
joblib.dump(clf, "ml/classifier.pkl")
print("Artifacts saved: ml/vectorizer.pkl, ml/classifier.pkl")
