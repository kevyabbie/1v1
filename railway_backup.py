from railway_backup import (

    setup_railway_backup_commands,

    railway_auto_backup_on_startup

)

BACKUP_CHANNEL_ID = 1460445504860192901 # Your channel ID

# In setup

setup_railway_backup_commands(tree, client, BACKUP_CHANNEL_ID)

# In on_ready

await railway_auto_backup_on_startup(client, BACKUP_CHANNEL_ID)

```

---

## 📦 How It Works

### Auto-Backup on Every Start

Bot uploads backup files to Discord:

- multi_mode_stats_auto_TIMESTAMP.json

- player_profiles_auto_TIMESTAMP.json

### Discord Commands

**Create Manual Backup (Before Updates):**

```

/backup

```

Uploads files to your backup channel with 🔒 MANUAL tag.

**Backup Specific User:**

```

/backupuser 822110342724190258

```

Uploads just that user's data.

**Restore from Backup:**

1. Find backup message in your backup channel

2. **Reply to it** with /restore

3. Bot downloads files and restores data

4. Restart bot on Railway

---

## 🔄 Example Workflow

### Before Update:

```

You: /backup

Bot: [Uploads files to #bot-backups]
