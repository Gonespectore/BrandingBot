# BrandingBot
# 🤖 Telegram Advanced Bot - Documentation

## 📋 Vue d'ensemble

Bot Telegram ultra-puissant avec capacités de traitement massif (100+ messages simultanés), publication automatique vers canaux, et système de transformation de messages avancé.

## ✨ Fonctionnalités

### 🎯 Transformations de Messages
- **Préfixe/Suffixe** : Ajoutez automatiquement du texte avant/après vos messages
- **Remplacement de Mots-clés** : Détectez et remplacez automatiquement des mots ou phrases spécifiques
- **Combinaisons** : Utilisez toutes les transformations simultanément

### 📢 Mode Publication
- Publiez automatiquement vos messages transformés dans un canal/groupe
- Le bot doit être administrateur du canal cible
- Pas de réponse dans le chat d'origine en mode publication

### ⚡ Traitement Massif
- Traitez jusqu'à **100+ messages simultanément**
- Système de buffer intelligent
- Barre de progression en temps réel
- Gestion automatique des rate limits Telegram
- Retry automatique en cas d'erreur

### 🎨 Interface Interactive
- Menu principal avec images aléatoires
- Navigation intuitive par boutons
- Confirmation visuelle de chaque action
- Statut en temps réel de vos paramètres

## 🚀 Installation sur Railway

### 1. Prérequis
- Compte Railway (railway.app)
- Bot Telegram créé via @BotFather
- Token du bot

### 2. Configuration

#### Variables d'environnement requises :
```bash
TELEGRAM_BOT_TOKEN=votre_token_ici
WEBHOOK_URL=https://votre-app.up.railway.app/webhook
DATABASE_URL=postgresql://user:pass@host:port/db  # Automatique avec Railway Postgres
```

#### Ajouter une base de données PostgreSQL :
1. Dans votre projet Railway, cliquez sur "New"
2. Sélectionnez "Database" → "Add PostgreSQL"
3. La variable `DATABASE_URL` sera automatiquement créée

### 3. Déploiement

#### Structure des fichiers :
```
projet/
├── main.py
├── db.py
├── handlers.py
├── keyboards.py
├── message_processor.py
├── requirements.txt
└── README.md
```

#### Déployer :
1. Connectez votre repo GitHub à Railway
2. Railway détectera automatiquement Python
3. Les dépendances seront installées automatiquement
4. Le bot démarrera sur le port 8000

## 📖 Guide d'utilisation

### Commandes disponibles

#### `/start` ou `/help`
Lance le bot et affiche le menu principal interactif avec une image.

#### `/process`
Mode traitement en lot :
- `/process` - Active le mode buffer
- Envoyez vos messages (max 100)
- `/process done` - Lance le traitement
- `/process cancel` - Annule
- `/process status` - Voir le nombre de messages en attente

#### `/stats`
Affiche vos statistiques personnelles et l'état de vos paramètres.

### Utilisation du Menu Interactif

#### 📝 Gestion du Préfixe
1. Cliquez sur "📝 Préfixe"
2. Choisissez "✏️ Définir préfixe"
3. Envoyez le texte souhaité
4. Exemple : `[PROMO] ` → Tous vos messages commenceront par `[PROMO]`

#### 📌 Gestion du Suffixe
1. Cliquez sur "📌 Suffixe"
2. Choisissez "✏️ Définir suffixe"
3. Envoyez le texte souhaité
4. Exemple : ` - Urgent!` → Tous vos messages se termineront par ` - Urgent!`

#### 🔄 Remplacement de Mots-clés
1. Cliquez sur "🔄 Remplacement"
2. Définissez le mot à chercher
3. Définissez le texte de remplacement
4. Exemple : Remplacer `prix` par `tarif exclusif`

#### 📢 Mode Publication
1. Cliquez sur "📢 Mode Publication"
2. Définissez d'abord le canal cible (ID du canal)
3. Activez le mode
4. Tous vos messages seront publiés dans le canal

**Comment obtenir l'ID d'un canal :**
1. Ajoutez @userinfobot à votre canal
2. Forwardez un message du canal vers @userinfobot
3. Il vous donnera l'ID (ex: `-1001234567890`)
4. Le bot doit être administrateur du canal

## 💡 Exemples d'utilisation

### Exemple 1 : Bot de promotions
```
Préfixe : 🎉 PROMO 
Suffixe :  - Offre limitée! 🔥
Mot-clé : acheter → réserver maintenant

Message original : "acheter ce produit"
Résultat : "🎉 PROMO réserver maintenant ce produit - Offre limitée! 🔥"
```

### Exemple 2 : Publication automatique
```
Mode publication : Activé
Canal cible : -1001234567890
Préfixe : [ANNONCE] 

Vous envoyez : "Nouveau produit disponible"
Le bot publie dans le canal : "[ANNONCE] Nouveau produit disponible"
```

### Exemple 3 : Traitement massif
```bash
/process
# Envoyez 100 messages
Message 1
Message 2
...
Message 100
/process done
```

Le bot traitera tous les messages avec vos paramètres :
- ✅ Barre de progression en temps réel
- ✅ Statistiques finales
- ✅ Gestion automatique des erreurs

## 🔧 Architecture technique

### Traitement parallèle
- **Semaphore** : Contrôle le nombre de messages traités simultanément (20 par défaut)
- **Rate limiting** : Délai automatique entre messages (0.03s)
- **Retry automatique** : 3 tentatives en cas d'erreur
- **Gestion RetryAfter** : Respect des limites Telegram

### Base de données
```sql
Table: user_preferences
- user_id (BigInteger) : ID Telegram unique
- prefix (Text) : Préfixe à ajouter
- suffix (Text) : Suffixe à ajouter
- keyword_find (Text) : Mot-clé à chercher
- keyword_replace (Text) : Texte de remplacement
- publish_mode (Boolean) : Mode publication activé
- target_chat_id (BigInteger) : ID du canal cible
- updated_at (DateTime) : Dernière modification
```

### Endpoints API

#### `GET /`
Health check et informations sur le bot

#### `POST /webhook`
Endpoint recevant les updates Telegram

#### `GET /stats`
Statistiques globales du bot

## 🛠️ Configuration avancée

### Ajuster la performance

Dans `message_processor.py` :
```python
# Modifier le nombre de messages simultanés
message_processor = MessageProcessor(
    max_concurrent=20,  # Augmentez pour plus de vitesse
    rate_limit_delay=0.03  # Diminuez avec prudence
)
```

### Personnaliser les images de bienvenue

Dans `handlers.py` :
```python
WELCOME_IMAGES = [
    "https://votre-image-1.jpg",
    "https://votre-image-2.jpg",
    # Ajoutez vos propres images
]
```

## 🐛 Résolution de problèmes

### Le webhook ne fonctionne pas
```bash
# Vérifiez dans les logs Railway :
✅ Webhook configuré: https://...
```

Si ce message n'apparaît pas :
1. Vérifiez que `WEBHOOK_URL` est correctement défini
2. Assurez-vous que l'URL est accessible publiquement
3. Testez avec `curl https://votre-app.up.railway.app/`

### Erreur "chat not found"
Le bot n'est pas administrateur du canal ou l'ID est incorrect :
1. Ajoutez le bot au canal
2. Faites-le administrateur
3. Vérifiez l'ID avec @userinfobot

### Rate limit atteint
Le bot attend automatiquement, mais vous pouvez :
1. Réduire `max_concurrent` dans `message_processor.py`
2. Augmenter `rate_limit_delay`

### Base de données non connectée
```bash
# Vérifiez dans Railway que PostgreSQL est bien ajouté
# La variable DATABASE_URL doit être présente
```

## 📊 Performances

- **Messages/seconde** : ~30-40 avec réglages par défaut
- **Concurrence** : 20 messages traités simultanément
- **Capacité buffer** : 100 messages
- **Rate limit handling** : Automatique avec retry

## 🔐 Sécurité

- ✅ Chaque utilisateur a ses propres paramètres isolés
- ✅ Validation des IDs de canaux
- ✅ Gestion sécurisée des erreurs
- ✅ Logs détaillés pour le débogage

## 📝 Logs

Les logs incluent :
- ✅ Configuration du webhook
- ✅ Traitement des messages
- ✅ Erreurs avec stack traces
- ✅ Rate limits et retries

## 🆘 Support

Pour toute question :
1. Consultez les logs dans Railway
2. Vérifiez les variables d'environnement
3. Testez avec `/stats` pour voir l'état

## 📄 Licence

Libre d'utilisation et de modification.