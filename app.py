import os
import json
import time
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
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
ICONS_CONFIG_FILE = "icons_config.json"

# Configuration par défaut des icônes
DEFAULT_ICONS = {
    "trophies": "https://media.brawltime.ninja/trophies.png",
    "level": "https://media.brawltime.ninja/level.png",
    "3vs3": "https://media.brawltime.ninja/3vs3.png",
    "solo": "https://media.brawltime.ninja/solo.png",
    "duo": "https://media.brawltime.ninja/duo.png",
    "club": "https://media.brawltime.ninja/club.png",
    "brawlers": "https://media.brawltime.ninja/brawlers.png"
}

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

def load_icons():
    if os.path.exists(ICONS_CONFIG_FILE):
        with open(ICONS_CONFIG_FILE, 'r') as f:
            return json.load(f)
    # Créer le fichier avec les icônes par défaut si n'existe pas
    save_icons(DEFAULT_ICONS)
    return DEFAULT_ICONS

def save_icons(icons):
    with open(ICONS_CONFIG_FILE, 'w') as f:
        json.dump(icons, f, indent=4)

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
    def __init__(self, api_key=None):
        # Clé API par défaut si aucune n'est fournie
        self.api_key = api_key or "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjczNTU5OGIxLWU4NGQtNDUwMy1hMWU4LTljZWIzNzczZjNkMSIsImlhdCI6MTc0MDY1MjM3NSwic3ViIjoiZGV2ZWxvcGVyLzNjYWIwYTBhLWQyMDktNmRlYi0yNTRiLWQxZmJmODIxYjFlMCIsInNjb3BlcyI6WyJicmF3bHN0YXJzIl0sImxpbWl0cyI6W3sidGllciI6ImRldmVsb3Blci9zaWx2ZXIiLCJ0eXBlIjoidGhyb3R0bGluZyJ9LHsiY2lkcnMiOlsiMTk1LjIyMC4wLjU4Il0sInR5cGUiOiJjbGllbnQifV19.qv_pyCCg1Z8oNmla8Dv6pBDTUThbYkjV4jQQwLYtVswH6hls5skQuCSXP5bYdWcFvLxleHyJw9mkm-NtYzojfQ"
        self.base_url = "https://api.brawlstars.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        self.history_file = "player_history.json"
        self.max_retries = 3
        self.retry_delay = 1  # délai en secondes
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
            clean_tag = self.clean_player_tag(tag)
            player_url = f"{self.base_url}/players/%23{clean_tag}"
            
            # Tentatives de connexion avec délai
            for attempt in range(self.max_retries):
                try:
                    print(f"URL de l'API: {player_url}")
                    print(f"Headers: {self.headers}")
                    
                    response = requests.get(player_url, headers=self.headers, timeout=10)
                    print(f"Status code: {response.status_code}")
                    print(f"Response: {response.text}")
                    
                    if response.status_code == 403:
                        return {"error": "Accès refusé. La clé API n'est pas valide ou a expiré."}
                    elif response.status_code == 404:
                        return {"error": "Joueur non trouvé. Vérifiez que le tag est correct."}
                    elif response.status_code == 429:
                        return {"error": "Trop de requêtes. Veuillez réessayer dans quelques minutes."}
                    elif response.status_code == 503:
                        return {"error": "Le service Brawl Stars est temporairement indisponible."}
                    elif response.status_code != 200:
                        return {"error": f"Erreur {response.status_code}: {response.text}"}
                    
                    break  # Sortir de la boucle si la requête réussit
                    
                except requests.exceptions.ConnectionError:
                    if attempt == self.max_retries - 1:  # Dernière tentative
                        return {"error": "Impossible de se connecter à l'API Brawl Stars. Vérifiez votre connexion internet."}
                    time.sleep(self.retry_delay * (attempt + 1))  # Délai progressif
                    continue
                    
                except requests.exceptions.Timeout:
                    if attempt == self.max_retries - 1:
                        return {"error": "Le serveur Brawl Stars met trop de temps à répondre. Réessayez plus tard."}
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
            
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

            player_data = {
                'tag': data['tag'],
                'name': data['name'],
                'trophies': data['trophies'],
                'expLevel': data.get('expLevel', 0),
                '3vs3Victories': data.get('3vs3Victories', 0),
                'soloVictories': data.get('soloVictories', 0),
                'duoVictories': data.get('duoVictories', 0),
                'club': data.get('club', None),
                'brawlers': data.get('brawlers', []),
                'icon': data.get('icon', None)
            }

            return player_data
        except Exception as e:
            print(f"Erreur lors de la récupération des informations du joueur: {e}")
            return {"error": "Une erreur inattendue s'est produite. Réessayez plus tard."}

# Création de l'instance de l'API
brawl_stars_api = BrawlStarsAPI()

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
    icons = load_icons()
    return render_template('admin.html',
                         current_api_key=brawl_stars_api.api_key,
                         auto_update_tags=load_auto_update_tags(),
                         is_super_admin=is_super,
                         admin_users=admin_users,
                         tag_history=tag_history,
                         icons=icons)

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

@app.route('/player_history/<tag>')
def get_player_history(tag):
    try:
        # Nettoyer le tag
        clean_tag = brawl_stars_api.clean_player_tag(tag)
        # Charger l'historique
        brawl_stars_api.load_history()
        # Récupérer l'historique du joueur
        history = brawl_stars_api.history.get(clean_tag, [])
        return jsonify(history)
    except Exception as e:
        print(f"Erreur lors de la récupération de l'historique: {e}")
        return jsonify([])

@app.route('/admin/upload_icon', methods=['POST'])
@admin_required
def upload_icon():
    category = request.form.get('category')
    file = request.files.get('file')
    
    if not category or not file:
        return jsonify({'success': False, 'error': 'Catégorie et fichier requis'}), 400
    
    try:
        # Créer le dossier static/img s'il n'existe pas
        upload_folder = os.path.join('static', 'img')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Vérifier que le fichier est une image
        if not file.content_type.startswith('image/'):
            return jsonify({'success': False, 'error': 'Le fichier doit être une image'}), 400
        
        # Sauvegarder le fichier
        filename = f"{category}.png"
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Mettre à jour la configuration des icônes
        icons = load_icons()
        icons[category] = f"/static/img/{filename}"
        save_icons(icons)
        
        return jsonify({
            'success': True,
            'message': 'Icône mise à jour avec succès',
            'path': f"/static/img/{filename}"
        })
        
    except Exception as e:
        print(f"Erreur lors de la mise à jour de l'icône: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reset_icons', methods=['POST'])
@admin_required
def reset_icons():
    save_icons(DEFAULT_ICONS)
    return jsonify({'success': True, 'message': 'Icônes réinitialisées avec succès'})

@app.route('/get_icons')
def get_icons():
    return jsonify(load_icons())

if __name__ == '__main__':
    app.run(debug=True) 