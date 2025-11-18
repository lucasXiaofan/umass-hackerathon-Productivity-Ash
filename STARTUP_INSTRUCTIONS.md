# How to Run Background Handler on Startup

## Automatic Startup (Recommended)

The LaunchAgent file has been created at:
`~/Library/LaunchAgents/com.classifier.background.plist`

### To Enable Auto-Start:

1. **Load the LaunchAgent:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.classifier.background.plist
   ```

2. **Verify it's running:**
   ```bash
   launchctl list | grep classifier
   ```

3. **Check logs (if needed):**
   ```bash
   tail -f ~/Documents/github_repos/hackathon-umass/logs/background_handler.log
   ```

### To Disable Auto-Start:

```bash
launchctl unload ~/Library/LaunchAgents/com.classifier.background.plist
```

### To Restart:

```bash
launchctl unload ~/Library/LaunchAgents/com.classifier.background.plist
launchctl load ~/Library/LaunchAgents/com.classifier.background.plist
```

---

## Manual Startup (Alternative)

If you prefer to start manually:

```bash
cd ~/Documents/github_repos/hackathon-umass/src
python3 background_handler_simple.py
```

---

## Shortcuts Available:

1. **Cmd+Shift+E** → Quick text note
   - Type 'C' for 40min timer
   - Type 'S' for 25min timer

2. **Cmd+Shift+4** → Regional screenshot + comment
   - Automatically copies to clipboard
   - You can paste with Cmd+V anywhere

---

## Troubleshooting:

### If shortcuts don't work:
1. Check System Preferences → Security & Privacy → Privacy → Accessibility
2. Make sure Terminal or Python has accessibility permissions

### If it crashes on startup:
```bash
# Check error logs
cat ~/Documents/github_repos/hackathon-umass/logs/background_handler.error.log
```

### To manually start in foreground (for debugging):
```bash
cd ~/Documents/github_repos/hackathon-umass/src
python3 background_handler_simple.py
```
