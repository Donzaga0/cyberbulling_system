import nltk
import re

from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

nltk.download('punkt')
nltk.download('stopwords')

stemmer = PorterStemmer()

def preprocess_text(text):

    text = text.lower()

    text = re.sub(r'[^a-zA-Z ]', '', text)

    tokens = word_tokenize(text)

    stop_words = set(stopwords.words('english'))

    tokens = [
        stemmer.stem(word)
        for word in tokens
        if word not in stop_words
    ]

    return " ".join(tokens)