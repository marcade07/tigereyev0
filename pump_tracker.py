# pumpfun_alert_tracker.py
import os
import json
import time
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify

# Load environment variables
load_dotenv()
WALLETS_TO_TRACK = set(addr.strip().lower() for addr in os.getenv("WALLETS_TO_TRACK", "").split(",")) | {
    "deuvj7xal3dsckcydhphbezivvyjgx­dmutl6ztyezz2e",
    "epf9ccvtggmqme1sxoczf1nmjxf5m1697ndpymibtu­c",
    "2sdfnsiesvsed8f4ftps2akvap4ctahfn5vy34gpq­q4b"
}
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_WEBHOOK_URL_2 = os.getenv("DISCORD_WEBHOOK_URL_2")
PUMPFUN_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")  

# Path to save seen bonding curves
SEEN_FILE = "seen_bonding_curves.json"

# Load seen tokens
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_tokens = set(json.load(f))
else:
    seen_tokens = set()

# Flask app
app = Flask(__name__)

def log(msg):
    print(f"[{time.ctime()}] {msg}")

# Groupes de wallets avec leurs couleurs
WALLET_GROUPS = {
    "orange": {
        "wallets": {
            "tj58bvn5nkreqkwnlbazmtgqj5y3og6qoxndywbhf5i",
            "3idbfbusnyvghdeqcnmg47v3abhcoshizpjzxswb4cdvj",
            "bn3hwjxmimiavxryu93tygrgnhmcgjat2ubwi3ydtpjaf",
            "emgwtjctu7g2azu4mrptcmazxuco3n3dnw6kvdqmzyhu"
        },
        "color": 16753920  # Orange
    },
    "yellow": {
        "wallets": {
            "cnrfd58zxkukqmncnwp4phoyj7znk4hd4yolq2jdutda",
            "hy1mvpeh6qytvbgnqrnfornqa6rpgxhjhmsqhe87qqj8"
        },
        "color": 16776960  # Jaune
    },
    "purple": {
        "wallets": {
            "6lrxdcvxmr8xkh6igjmf8vzzchmjltqjj8hkc8wwuyiq",
            "g5ujs33tlbzmpmvfehfwfdbeilusmj1mymoygqxtg7dz",
            "gycpvbkatdlimybxrzxzvnodvm2oxca8j74cpsbrybql",
            "6gxv1gdab9cy7gjkbhskssm3n44w5owmhg3rqb1d6unn"
        },
        "color": 8388736  # Violet
    },
    "green": {
        "wallets": {
            "deuvj7xal3dsckcydhphbezivvyjgx­dmutl6ztyezz2e",
            "epf9ccvtggmqme1sxoczf1nmjxf5m1697ndpymibtu­c",
            "2sdfnsiesvsed8f4ftps2akvap4ctahfn5vy34gpq­q4b"
        },
        "color": 65280  # Vert (#00FF00)
    }
}

# Send Discord alert with embed
def send_discord_alert(message, color):
    webhook_urls = [DISCORD_WEBHOOK_URL, DISCORD_WEBHOOK_URL_2]
    embed = {
        "description": message,
        "color": color
    }
    payload = {
        "embeds": [embed]
    }
    for url in webhook_urls:
        if url:
            try:
                res = requests.post(url, json=payload)
                if res.status_code == 204:
                    log(f"✅ Alerte envoyée sur Discord ({url[:30]}...)")
                else:
                    log(f"❌ Erreur Discord ({url[:30]}...) : {res.status_code}")
            except Exception as e:
                log(f"❌ Exception Discord ({url[:30]}...) : {e}")

# Récupérer les métadonnées du token (nom et ticker)
def get_token_metadata(mint_address):
    if not HELIUS_API_KEY:
        log("⚠️ Clé API Helius manquante")
        return "Inconnu", "Inconnu"
    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    payload = {
        "jsonrpc": "2.0",
        "id": "text",
        "method": "getAsset",
        "params": {
            "id": mint_address
        }
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        data = response.json()
        if "result" in data and "content" in data["result"] and "metadata" in data["result"]["content"]:
            metadata = data["result"]["content"]["metadata"]
            name = metadata.get("name", "Inconnu")
            symbol = metadata.get("symbol", "Inconnu")
            return name, symbol
        else:
            log(f"⚠️ Métadonnées non trouvées pour le mint {mint_address}")
            return "Inconnu", "Inconnu"
    except Exception as e:
        log(f"❌ Erreur lors de la récupération des métadonnées pour {mint_address} : {e}")
        return "Inconnu", "Inconnu"

# Dernier log "tracking en cours"
last_tracking_log_time = 0
TRACKING_LOG_INTERVAL = 1800  # 30 minutes

# Webhook endpoint
@app.route("/helius-webhook", methods=["POST"])
def helius_webhook():
    global last_tracking_log_time
    try:
        txs = request.json
        log(f"📥 Données webhook reçues : {json.dumps(txs, indent=2)}")
        current_time = time.time()
        if current_time - last_tracking_log_time >= TRACKING_LOG_INTERVAL:
            log("🛰️ Webhook Helius reçu — tracking toujours actif")
            last_tracking_log_time = current_time

        log(f"👛 Wallets suivis : {WALLETS_TO_TRACK}")

        for tx in txs:
            log(f"🔍 Analyse de la transaction : {json.dumps(tx, indent=2)}")
            accounts = tx.get("accountData", [])
            description = tx.get("description", "")

            # Vérifier Pump.fun via programId ou source
            instructions = tx.get("instructions", [])
            is_pumpfun = any(instr.get("programId") == PUMPFUN_PROGRAM_ID for instr in instructions) or tx.get("source") == "PUMP_FUN"
            log(f"🆔 Pump.fun détecté : {is_pumpfun}")
            if not is_pumpfun:
                log(f"⏩ Transaction ignorée (pas Pump.fun)")
                continue

            # Vérification des comptes impliqués et récupération du wallet tracké
            log(f"👤 Accounts dans la transaction : {[acc.get('account', '') for acc in accounts]}")
            involved_wallets = [acc.get("account", "") for acc in accounts if acc.get("account", "").lower() in WALLETS_TO_TRACK]
            if not involved_wallets:
                log(f"⏩ Transaction ignorée (aucun wallet suivi impliqué)")
                continue

            # Prendre le premier wallet tracké impliqué
            involved_wallet = involved_wallets[0].lower()
            log(f"👛 Wallet tracké impliqué : {involved_wallet}")

            # Déterminer la couleur en fonction du groupe du wallet
            color = 0  # Default (noir si aucun groupe ne correspond)
            for group, info in WALLET_GROUPS.items():
                if involved_wallet in info["wallets"]:
                    color = info["color"]
                    log(f"🎨 Couleur déterminée : {group} ({color})")
                    break
            if color == 0:
                log("⚠️ Aucun groupe de couleur trouvé pour ce wallet, utilisation de la couleur par défaut")

            # Récupération du mint
            base_mint = None
            for transfer in tx.get("tokenTransfers", []):
                if transfer.get("fromUserAccount", "").lower() in WALLETS_TO_TRACK or transfer.get("toUserAccount", "").lower() in WALLETS_TO_TRACK:
                    base_mint = transfer.get("mint")
                    log(f"🪙 Base mint trouvé dans tokenTransfers : {base_mint}")
                    break

            if not base_mint and "transferred" in description and "to" in description:
                parts = description.split("transferred")
                if len(parts) > 1:
                    subparts = parts[1].strip().split(" to ")
                    if len(subparts) > 1:
                        amount_and_mint = subparts[0].strip().split()
                        if len(amount_and_mint) > 1:
                            base_mint = amount_and_mint[-1]
                            log(f"🪙 Base mint extrait de description : {base_mint}")

            if not base_mint:
                log(f"⚠️ Impossible de détecter le base_mint")
                continue

            # Récupérer le nom et le ticker du token
            token_name, token_symbol = get_token_metadata(base_mint)

            mint_lower = base_mint.lower()
            if mint_lower in seen_tokens:
                log(f"🔁 Token déjà vu : {base_mint}")
                continue

            # Nouvelle bonding curve détectée
            seen_tokens.add(mint_lower)
            with open(SEEN_FILE, "w") as f:
                json.dump(list(seen_tokens), f)
            log(f"💾 Token {base_mint} ajouté aux vus")

            # Construire le message avec la date et l'heure
            current_time_str = time.ctime()  # Format identique aux logs
            message = f"🚨 Nouvelle interaction avec bonding curve Pump.fun !\n"
            message += f"👛 Wallet impliqué : `{involved_wallet}`\n"
            message += f"🪙 Token Mint: `{base_mint}`\n"
            message += f"📛 Nom: `{token_name}`\n"
            message += f"💱 Ticker: `{token_symbol}`\n"
            message += f"🔗 https://solscan.io/token/{base_mint}\n"
            message += f"⏰ Date et heure : `{current_time_str}`"

            log(f"📤 Envoi de l'alerte avec couleur {color} : {message}")
            send_discord_alert(message, color)

    except Exception as e:
        log(f"❌ Erreur traitement webhook : {e}")

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    log("🚀 Démarrage du serveur Flask")
    app.run(host="0.0.0.0", port=5001)