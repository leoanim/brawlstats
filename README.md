# BrawlStats

Une application web Python pour consulter les statistiques des joueurs de Brawl Stars.

## Installation de Python (Windows)

1. Téléchargez Python depuis https://www.python.org/downloads/
2. Lancez l'installateur
3. **IMPORTANT** : Cochez la case "Add Python to PATH" en bas de la fenêtre d'installation
4. Cliquez sur "Install Now"
5. Une fois l'installation terminée, ouvrez PowerShell ou CMD et vérifiez l'installation :
```bash
python --version
pip --version
```

Si les commandes fonctionnent, vous pouvez passer à l'installation de l'application.

## Installation de l'application

1. Ouvrez PowerShell ou CMD dans le dossier du projet
2. Créez un environnement virtuel :
```bash
python -m venv venv
```

3. Activez l'environnement virtuel :
```bash
.\venv\Scripts\activate
```

4. Installez les dépendances :
```bash
python -m pip install -r requirements.txt
```

## Lancement de l'application

1. Assurez-vous que l'environnement virtuel est activé (vous devriez voir `(venv)` au début de la ligne de commande)
2. Lancez l'application :
```bash
python app.py
```
3. Ouvrez votre navigateur à l'adresse `http://localhost:5000`

## Utilisation

1. Entrez le tag du joueur (avec ou sans le #) dans le champ de recherche
2. Cliquez sur "Rechercher" pour voir les statistiques du joueur
3. Les informations affichées incluent :
   - Nom du joueur
   - Tag
   - Nombre de trophées actuels
   - Record de trophées
   - Niveau d'expérience

## Résolution des problèmes

Si vous rencontrez des erreurs :
1. Vérifiez que Python est bien dans le PATH :
   - Ouvrez les Paramètres Windows
   - Recherchez "variables d'environnement"
   - Cliquez sur "Variables d'environnement"
   - Dans "Variables système", trouvez "Path"
   - Vérifiez que le chemin vers Python est présent (par exemple : C:\Users\[Votre_Nom]\AppData\Local\Programs\Python\Python3x\)

2. Si les commandes ne fonctionnent toujours pas :
   - Redémarrez votre terminal
   - Redémarrez votre ordinateur si nécessaire 