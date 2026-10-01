from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import secrets
import hashlib
import sqlite3
import warnings
import os

warnings.filterwarnings('ignore')

app = Flask(__name__)
app.secret_key = secrets.token_hex(16) 

print("=" * 80)
print("VOYAGEIA - Application de Recommandation de Destinations")
print("=" * 80)
print("Chargement des modules...")

def init_db():
    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_hash TEXT UNIQUE NOT NULL,
        pseudo TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS consents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_hash TEXT NOT NULL,
        consent_type TEXT NOT NULL,
        consent_given INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_hash TEXT,
        FOREIGN KEY (user_hash) REFERENCES users(user_hash)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_hash TEXT NOT NULL,
        budget TEXT,
        climat TEXT,
        type_activite TEXT,
        duree TEXT,
        continent TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_hash) REFERENCES users(user_hash)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_hash TEXT NOT NULL,
        destination TEXT NOT NULL,
        confidence REAL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_hash) REFERENCES users(user_hash)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS rgpd_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_hash TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    print("Base de données initialisée")

init_db()

def generate_dataset_from_csv(csv_path="destinations.csv"):
    print("Chargement du dataset depuis le CSV...")

    df = pd.read_csv(csv_path)

    df['Country'] = df['Country'].str.strip()
    df['Category'] = df['Category'].str.lower().str.strip()

    df = df.assign(Category=df['Category'].str.split(',')).explode('Category')
    df['Category'] = df['Category'].str.strip()

    continent_map = {
        'Europe': ['France', 'Spain', 'Italy', 'Germany', 'United Kingdom', 'Portugal', 'Greece',
                   'Netherlands', 'Switzerland', 'Austria', 'Czech Republic', 'Belgium', 'Sweden',
                   'Norway', 'Denmark', 'Ireland', 'Poland', 'Hungary'],
        'Asia': ['Japan', 'China', 'Thailand', 'Vietnam', 'Indonesia', 'Malaysia', 'Singapore',
                 'South Korea', 'India', 'Nepal', 'Sri Lanka', 'Israel', 'Turkey'],
        'North America': ['United States', 'Canada', 'Mexico'],
        'South America': ['Brazil', 'Argentina', 'Peru', 'Chile', 'Colombia'],
        'Oceania': ['Australia', 'New Zealand'],
        'Africa': ['Morocco', 'Egypt', 'South Africa', 'Kenya', 'Tanzania']
    }

    def get_continent(country):
        for cont, countries in continent_map.items():
            if country in countries:
                return cont
        return "Other"

    df['continent'] = df['Country'].apply(get_continent)

    def assign_budget(continent):
        if continent == 'Africa':
            return np.random.choice(['faible', 'moyen'])
        elif continent == 'Asia':
            return np.random.choice(['faible', 'moyen', 'élevé'])
        elif continent == 'Europe':
            return np.random.choice(['moyen', 'élevé', 'très élevé'])
        elif continent == 'North America':
            return np.random.choice(['moyen', 'élevé'])
        elif continent == 'South America':
            return np.random.choice(['faible', 'moyen'])
        elif continent == 'Oceania':
            return np.random.choice(['élevé', 'très élevé'])
        else:
            return 'moyen'

    df['budget'] = df['continent'].apply(assign_budget)

    def assign_climat(continent):
        if continent in ['Africa', 'South America']:
            return np.random.choice(['chaud', 'tropical'])
        elif continent in ['Europe']:
            return np.random.choice(['tempéré', 'froid'])
        elif continent in ['Asia']:
            return np.random.choice(['tropical', 'tempéré', 'chaud'])
        elif continent in ['Oceania']:
            return np.random.choice(['tempéré', 'tropical'])
        elif continent in ['North America']:
            return np.random.choice(['tempéré', 'froid', 'chaud'])
        else:
            return 'tempéré'

    df['climat'] = df['continent'].apply(assign_climat)

    df['duree'] = np.random.choice(['court', 'moyen', 'long'], len(df))

    df['type_activite'] = df['Category'].str.strip()

    df['destination'] = df['City']

    model_df = df[['budget', 'climat', 'type_activite', 'duree', 'continent', 'destination']]

    print(f"✅ Dataset créé à partir du CSV : {len(model_df)} échantillons ({df['City'].nunique()} villes)")
    return model_df, df['destination'].unique().tolist()


def get_unique_categories(df):
    all_categories = set()
    for cat_list in df['Category']:
        for c in cat_list.split(','):
            all_categories.add(c.strip().lower())
    return sorted(all_categories)

df, destinations_list = generate_dataset_from_csv("Database/travel_destinations.csv")
categories_list = get_unique_categories(pd.read_csv("Database/travel_destinations.csv"))



print("🤖 Entraînement du modèle d'IA...")


le_budget = LabelEncoder()
le_climat = LabelEncoder()
le_activite = LabelEncoder()
le_duree = LabelEncoder()
le_continent = LabelEncoder()
le_destination = LabelEncoder()

X = pd.DataFrame({
    'budget': le_budget.fit_transform(df['budget']),
    'climat': le_climat.fit_transform(df['climat']),
    'type_activite': le_activite.fit_transform(df['type_activite']),
    'duree': le_duree.fit_transform(df['duree']),
    'continent': le_continent.fit_transform(df['continent'])
})

y = le_destination.fit_transform(df['destination'])

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = DecisionTreeClassifier(max_depth=8, min_samples_split=10, random_state=42)
model.fit(X_train, y_train)

accuracy = int(model.score(X_test, y_test) * 100)
print(f"Modèle entraîné - Précision : {accuracy}%")

def get_or_create_user(pseudo, ip_address):
    pseudo_to_hash = pseudo if pseudo else f"anonymous_{ip_address}"
    user_hash = hashlib.sha256(pseudo_to_hash.encode()).hexdigest()[:16] 
    ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16] 
    
    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE user_hash = ?', (user_hash,))
    user = c.fetchone()
    
    if not user:
        c.execute('INSERT INTO users (user_hash, pseudo) VALUES (?, ?)', (user_hash, pseudo))
        conn.commit()
    else:
        c.execute('UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_hash = ?', (user_hash,))
        conn.commit()
    
    conn.close()
    return user_hash, ip_hash

def log_consent(user_hash, ip_hash):
    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    
    consent_types = ['data_processing', 'rights_informed', 'pseudonymisation_understood']
    for consent_type in consent_types:
        c.execute('''INSERT INTO consents (user_hash, consent_type, consent_given, ip_hash) 
                     VALUES (?, ?, 1, ?)''', (user_hash, consent_type, ip_hash))
    
    c.execute('''INSERT INTO rgpd_logs (user_hash, action, details) 
                  VALUES (?, 'CONSENT_GIVEN', 'Consentement complet obtenu (Art. 6.1.a)')''', (user_hash,))
    
    conn.commit()
    conn.close()

def save_preferences(user_hash, preferences):
    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    
    c.execute('''INSERT INTO preferences (user_hash, budget, climat, type_activite, duree, continent) 
                  VALUES (?, ?, ?, ?, ?, ?)''',
              (user_hash, preferences['budget'], preferences['climat'], 
               preferences['type_activite'], preferences['duree'], preferences['continent']))
    
    conn.commit()
    conn.close()

def save_recommendation(user_hash, destination, confidence):
    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    
    c.execute('''INSERT INTO recommendations (user_hash, destination, confidence) 
                  VALUES (?, ?, ?)''', (user_hash, destination, confidence))
    
    conn.commit()
    conn.close()

def get_user_data(user_hash):
    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE user_hash = ?', (user_hash,))
    user = c.fetchone()
    
    c.execute('SELECT * FROM preferences WHERE user_hash = ? ORDER BY timestamp DESC LIMIT 10', (user_hash,))
    preferences = c.fetchall()
    
    c.execute('SELECT * FROM recommendations WHERE user_hash = ? ORDER BY timestamp DESC LIMIT 10', (user_hash,))
    recommendations = c.fetchall()
    
    c.execute('SELECT * FROM consents WHERE user_hash = ?', (user_hash,))
    consents = c.fetchall()
    
    conn.close()
    
    return {
        'user': user,
        'preferences': preferences,
        'recommendations': recommendations,
        'consents': consents
    }

def delete_user_data(user_hash):
    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    
    c.execute('DELETE FROM preferences WHERE user_hash = ?', (user_hash,))
    c.execute('DELETE FROM recommendations WHERE user_hash = ?', (user_hash,))
    c.execute('DELETE FROM consents WHERE user_hash = ?', (user_hash,))
    c.execute('DELETE FROM users WHERE user_hash = ?', (user_hash,))
    
    c.execute('''INSERT INTO rgpd_logs (user_hash, action, details) 
                  VALUES (?, 'DATA_DELETED', 'Suppression complète des données utilisateur (Art. 17)')''', 
              (user_hash,))
    
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM recommendations')
    total_recommendations = c.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_recommendations': total_recommendations,
        'accuracy': accuracy 
    }

@app.route('/')
def index():
    stats = get_stats()
    recommendation_result = request.args.get('result')
    confidence_score = request.args.get('confidence')
    error_message = request.args.get('error')

    categories_list = sorted(list(le_activite.classes_))

    return render_template('index.html',
                           stats=stats,
                           recommendation_result=recommendation_result,
                           confidence_score=confidence_score,
                           error_message=error_message,
                           categories=categories_list)



@app.route('/recommend', methods=['POST'])
def recommend():
    data = {} 
    try:
        data = request.get_json(force=True) or {}

        pseudo = data.get('pseudo', '').strip()
        user_hash, ip_hash = get_or_create_user(pseudo, request.remote_addr)

        if 'logged_consent' not in session:
            log_consent(user_hash, ip_hash)
            session['logged_consent'] = True

        continent_map_fr_en = {
            "europe": "Europe",
            "asie": "Asia",
            "amérique du nord": "North America",
            "amérique du sud": "South America",
            "océanie": "Oceania"
        }
        continent_fr = data.get('continent', '').strip().lower()
        continent_en = continent_map_fr_en.get(continent_fr, continent_fr)

        preferences = {
            'budget': data.get('budget', '').strip().lower(),
            'climat': data.get('climat', '').strip().lower(),
            'type_activite': data.get('activite', '').strip().lower(),
            'duree': data.get('duree', '').strip().lower(),
            'continent': continent_en
        }

        save_preferences(user_hash, preferences)

        for key, le in [
            ('budget', le_budget),
            ('climat', le_climat),
            ('type_activite', le_activite),
            ('duree', le_duree),
            ('continent', le_continent)
        ]:
            if preferences[key] not in le.classes_:
                return jsonify({
                    'destination': None,
                    'confidence': 0,
                    'error': f"Valeur invalide pour {key}: {preferences[key]}"
                })

        user_input = pd.DataFrame([{
            'budget': le_budget.transform([preferences['budget']])[0],
            'climat': le_climat.transform([preferences['climat']])[0],
            'type_activite': le_activite.transform([preferences['type_activite']])[0],
            'duree': le_duree.transform([preferences['duree']])[0],
            'continent': le_continent.transform([preferences['continent']])[0]
        }])

        prediction_index = model.predict(user_input)[0]
        destination = le_destination.inverse_transform([prediction_index])[0]
        confidence = int(np.max(model.predict_proba(user_input)[0]) * 100)

        save_recommendation(user_hash, destination, confidence)

        return jsonify({
            'destination': destination,
            'confidence': confidence,
            'error': None
        })

    except Exception as e:
        print(f"Erreur interne: {e}")
        return jsonify({
            'error': "Une erreur interne est survenue.",
            'destination': None,
            'confidence': 0
        }), 500


@app.route('/rgpd/data-request', methods=['POST'])
def data_request():
    identifier = request.get_json().get('identifier')
    
    if not identifier:
        return jsonify({'error': "Identifiant (Pseudonyme ou Hash) manquant."}), 400
    
    user_hash = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
    data = get_user_data(user_hash)
    
    if not data['user']:
        conn = sqlite3.connect('voyageia.db')
        c = conn.cursor()
        c.execute('''INSERT INTO rgpd_logs (user_hash, action, details) 
                     VALUES (?, 'DATA_REQUEST_FAILED', 'Tentative par: ' || ?)''', ('unknown_or_deleted', identifier))
        conn.commit()
        conn.close()
        
        return jsonify({'error': "Aucune donnée trouvée pour cet identifiant (Vérifiez votre pseudonyme).", 'data': None}), 404

    conn = sqlite3.connect('voyageia.db')
    c = conn.cursor()
    c.execute('''INSERT INTO rgpd_logs (user_hash, action, details) 
                 VALUES (?, 'DATA_REQUEST_SUCCESS', 'Données fournies (Art. 15)')''', (user_hash,))
    conn.commit()
    conn.close()

    formatted_data = {
        'user_hash': user_hash,
        'pseudo_saisi': identifier,
        'informations_utilisateur': {
            'pseudo_stocke': data['user'][2],
            'date_creation': data['user'][3],
            'derniere_activite': data['user'][4],
        },
        'historique_preferences': data['preferences'],
        'historique_recommandations': data['recommendations'],
        'preuves_consentement': data['consents']
    }
    
    return jsonify({'data': formatted_data})


@app.route('/rgpd/data-deletion', methods=['POST'])
def data_deletion():
    identifier = request.get_json().get('identifier')
    
    if not identifier:
        return jsonify({'error': "Identifiant manquant."}), 400
        
    user_hash = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
    data = get_user_data(user_hash)
    if not data['user']:
        return jsonify({'error': "Aucune donnée trouvée pour cet identifiant (Vérifiez votre pseudonyme)."})
        
    delete_user_data(user_hash)
    
    return jsonify({'message': f"Toutes les données associées à l'identifiant **{identifier}** (Hash: {user_hash}) ont été effacées. (Art. 17 RGPD)"})

if __name__ == '__main__':
    app.run(debug=True)
