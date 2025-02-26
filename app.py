from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import time
from functools import wraps
import threading
import schedule

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-secret-key')  # À changer en production

# Fichiers de configuration
AUTO_UPDATE_TAGS_FILE = "auto_update_tags.json"
ADMIN_USERS_FILE = "admin_users.json"
TAG_HISTORY_FILE = "tag_history.json"

# Variable pour suivre la dernière mise à jour
LAST_UPDATE_TIME = time.time()

# Charger les administrateurs depuis le fichier JSON
def load_admin_users():
    if os.path.exists(ADMIN_USERS_FILE):
        with open(ADMIN_USERS_FILE, 'r') as f:
            return json.load(f)
    # Créer le fichier avec l'admin par défaut si n'existe pas
    default_admin = {
        'leoanim': {
            'password': '1234',
            'is_super_admin': True
        }
    }
    save_admin_users(default_admin)
    return default_admin

def save_admin_users(admin_users):
    with open(ADMIN_USERS_FILE, 'w') as f:
        json.dump(admin_users, f, indent=4)

# Fonction pour vérifier si un utilisateur est super admin
def is_super_admin():
    if not session.get('admin_logged_in'):
        return False
    admin_users = load_admin_users()
    username = session.get('admin_username')
    return admin_users.get(username, {}).get('is_super_admin', False)

def load_auto_update_tags():
    if os.path.exists(AUTO_UPDATE_TAGS_FILE):
        with open(AUTO_UPDATE_TAGS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_auto_update_tags(tags):
    with open(AUTO_UPDATE_TAGS_FILE, 'w') as f:
        json.dump(tags, f)

def load_tag_history():
    if os.path.exists(TAG_HISTORY_FILE):
        with open(TAG_HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def save_tag_history(history):
    with open(TAG_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)

def add_to_history(tag, action, admin_username):
    history = load_tag_history()
    history.append({
        'tag': tag,
        'action': action,
        'admin': admin_username,
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    })
    save_tag_history(history)

# Décorateur pour protéger les routes admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Décorateur pour les routes super admin
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_super_admin():
            return redirect(url_for('admin_panel'))
        return f(*args, **kwargs)
    return decorated_function

class BrawlStarsAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.brawlstars.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        self.history_file = "player_history.json"
        self.load_history()

    def load_history(self):
        """Charge l'historique des joueurs depuis le fichier JSON"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
            else:
                self.history = {}
        except:
            self.history = {}

    def save_history(self):
        """Sauvegarde l'historique des joueurs dans le fichier JSON"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f)

    def update_player_history(self, tag, data):
        """Met à jour l'historique d'un joueur avec les nouvelles données"""
        if tag not in self.history:
            self.history[tag] = []

        current_time = int(time.time())
        new_entry = {
            'timestamp': current_time,
            'date': datetime.fromtimestamp(current_time).strftime('%d/%m/%Y'),
            'trophies': data['trophies'],
            'highestTrophies': data.get('highestTrophies', data['trophies'])
        }

        # Ajouter la nouvelle entrée si c'est la première ou si les trophées ont changé
        if not self.history[tag] or self.history[tag][-1]['trophies'] != new_entry['trophies']:
            self.history[tag].append(new_entry)
            self.save_history()

        # Calculer la tendance
        if len(self.history[tag]) > 1:
            trend = new_entry['trophies'] - self.history[tag][-2]['trophies']
        else:
            trend = 0

        return trend

    def clean_player_tag(self, tag):
        """Nettoie et formate le tag du joueur."""
        tag = tag.strip().upper()
        if tag.startswith('#'):
            tag = tag[1:]
        return tag

    def get_player_info(self, tag):
        try:
            # Nettoyage du tag
            clean_tag = tag.upper().replace('#', '')
            
            # Récupération des informations du joueur
            player_url = f"{self.base_url}/players/%23{clean_tag}"
            response = requests.get(player_url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"Erreur API: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            
            # Récupération des informations du club si le joueur est dans un club
            club_info = None
            if 'club' in data and data['club'].get('tag'):
                club_tag = data['club']['tag'].replace('#', '')
                club_url = f"{self.base_url}/clubs/%23{club_tag}"
                club_response = requests.get(club_url, headers=self.headers)
                if club_response.status_code == 200:
                    club_info = club_response.json()
                    data['club']['members'] = club_info.get('members', [])
                    data['club']['description'] = club_info.get('description', '')

            # Calcul de la progression des brawlers
            total_brawlers = len(data['brawlers'])
            max_power_brawlers = sum(1 for b in data['brawlers'] if b['power'] == 11)
            progress_percentage = round((max_power_brawlers / total_brawlers) * 100, 1)

            # Enrichissement des données des brawlers
            for brawler in data['brawlers']:
                # Ajout des URLs des icônes
                brawler['iconUrl'] = f"https://media.brawltime.ninja/brawlers/{brawler['id']}.png"
                
                # Calcul du pourcentage de progression
                progress = (brawler['power'] / 11) * 100
                brawler['progress_percentage'] = round(progress, 1)

                # Initialisation des listes si non présentes
                brawler.setdefault('gadgets', [])
                brawler.setdefault('starPowers', [])
                brawler.setdefault('gears', [])

            # Ajout des informations de progression
            data['brawler_progress'] = {
                'total': total_brawlers,
                'max_power': max_power_brawlers,
                'percentage': progress_percentage
            }

            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des informations du joueur: {e}")
            return None

# Création de l'instance de l'API
brawl_stars_api = BrawlStarsAPI(os.getenv('BRAWL_STARS_API_KEY'))

# Fonction d'actualisation automatique
def auto_update_players():
    global LAST_UPDATE_TIME
    tags = load_auto_update_tags()
    for tag in tags:
        try:
            brawl_stars_api.get_player_info(tag)
            time.sleep(1)  # Pause pour éviter de surcharger l'API
        except Exception as e:
            print(f"Erreur lors de l'actualisation automatique pour {tag}: {str(e)}")
    LAST_UPDATE_TIME = time.time()

# Démarrage de l'actualisation automatique
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(60)

schedule.every(1).hour.do(auto_update_players)
scheduler_thread = threading.Thread(target=run_schedule)
scheduler_thread.daemon = True
scheduler_thread.start()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search_player', methods=['POST'])
def search_player():
    player_tag = request.form.get('player_tag', '')
    data = brawl_stars_api.get_player_info(player_tag)
    if data:
        return jsonify(data)
    else:
        return jsonify({'error': 'Erreur lors de la récupération des informations du joueur'}), 500

@app.route('/admin/login', methods=['POST'])
def admin_login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    admin_users = load_admin_users()
    if username in admin_users and admin_users[username]['password'] == password:
        session['admin_logged_in'] = True
        session['admin_username'] = username
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Identifiants invalides'}), 401

@app.route('/admin')
@admin_required
def admin_panel():
    is_super = is_super_admin()
    admin_users = load_admin_users() if is_super else {}
    tag_history = load_tag_history()
    return render_template('admin.html',
                         current_api_key=brawl_stars_api.api_key,
                         auto_update_tags=load_auto_update_tags(),
                         is_super_admin=is_super,
                         admin_users=admin_users,
                         tag_history=tag_history)

@app.route('/admin/update_api_key', methods=['POST'])
@admin_required
def update_api_key():
    new_api_key = request.form.get('api_key')
    if new_api_key:
        brawl_stars_api.api_key = new_api_key
        brawl_stars_api.headers['Authorization'] = f'Bearer {new_api_key}'
        return redirect(url_for('admin_panel'))
    return 'Clé API invalide', 400

@app.route('/admin/add_tag', methods=['POST'])
@admin_required
def add_tag():
    tag = request.form.get('tag')
    if tag:
        tags = load_auto_update_tags()
        clean_tag = brawl_stars_api.clean_player_tag(tag)
        if clean_tag not in tags:
            tags.append(clean_tag)
            save_auto_update_tags(tags)
            add_to_history(clean_tag, 'ajout', session.get('admin_username'))
            return jsonify({'success': True, 'message': 'Tag ajouté avec succès'})
    return jsonify({'success': False, 'error': 'Tag invalide ou déjà existant'}), 400

@app.route('/admin/remove_tag', methods=['POST'])
@admin_required
def remove_tag():
    tag = request.form.get('tag')
    if tag:
        tags = load_auto_update_tags()
        if tag in tags:
            tags.remove(tag)
            save_auto_update_tags(tags)
            add_to_history(tag, 'suppression', session.get('admin_username'))
            return jsonify({'success': True, 'message': 'Tag supprimé avec succès'})
    return jsonify({'success': False, 'error': 'Tag non trouvé'}), 404

@app.route('/admin/add_admin', methods=['POST'])
@admin_required
@super_admin_required
def add_admin():
    username = request.form.get('username')
    password = request.form.get('password')
    is_super = request.form.get('is_super_admin') == 'true'
    
    if username and password:
        admin_users = load_admin_users()
        if username not in admin_users:
            admin_users[username] = {
                'password': password,
                'is_super_admin': is_super
            }
            save_admin_users(admin_users)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Cet utilisateur existe déjà'}), 400
    return jsonify({'success': False, 'error': 'Nom d\'utilisateur et mot de passe requis'}), 400

@app.route('/admin/remove_admin', methods=['POST'])
@admin_required
@super_admin_required
def remove_admin():
    username = request.form.get('username')
    admin_users = load_admin_users()
    
    # Empêcher la suppression du dernier super admin
    if username in admin_users:
        if admin_users[username].get('is_super_admin'):
            super_admin_count = sum(1 for user in admin_users.values() if user.get('is_super_admin'))
            if super_admin_count <= 1:
                return jsonify({'success': False, 'error': 'Impossible de supprimer le dernier super administrateur'}), 400
        
        del admin_users[username]
        save_admin_users(admin_users)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Administrateur non trouvé'}), 404

@app.route('/admin/next_update')
@admin_required
def get_next_update():
    current_time = time.time()
    elapsed = int(current_time - LAST_UPDATE_TIME)
    next_update = 3600 - (elapsed % 3600)  # 3600 secondes = 1 heure
    return jsonify({
        'next_update': next_update,
        'last_update': int(LAST_UPDATE_TIME)
    })

@app.route('/admin/update_tag', methods=['POST'])
@admin_required
def update_tag_manually():
    tag = request.form.get('tag')
    if tag:
        try:
            data = brawl_stars_api.get_player_info(tag)
            if data:
                add_to_history(tag, 'actualisation', session.get('admin_username'))
                return jsonify({'success': True, 'message': 'Tag actualisé avec succès'})
            return jsonify({'success': False, 'error': 'Erreur lors de la récupération des informations du joueur'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': 'Tag non fourni'}), 400

if __name__ == '__main__':
    app.run(debug=True) 