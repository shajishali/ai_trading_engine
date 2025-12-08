# Server Access Setup Guide
**Server IP**: 52.221.248.235  
**Username**: ubuntu  
**Key File**: PEM file (in Downloads folder)

---

## Step 1: Convert PEM Key to PuTTY Format (.ppk)

### Using PuTTYgen:

1. **Open PuTTYgen** (should be installed with PuTTY)
   - If not installed, download from: https://www.putty.org/

2. **Load your PEM key**:
   - Click **Conversions** → **Import key**
   - Navigate to your Downloads folder
   - Select your PEM file (usually named something like `key.pem` or `server-key.pem`)
   - Click **Open**

3. **Save as PuTTY format**:
   - Click **Save private key**
   - **Save location**: Save to a secure location (recommended: `C:\Users\YourUsername\.ssh\trading-engine-key.ppk`)
   - **File name**: `trading-engine-key.ppk`
   - Click **Save**
   - If prompted about saving without passphrase, click **Yes** (or set a passphrase for extra security)

4. **Optional - Set passphrase** (recommended for security):
   - Enter a strong passphrase in "Key passphrase" field
   - Re-enter in "Confirm passphrase" field
   - Then save the key

**Important**: Keep this `.ppk` file secure! Don't share it or commit it to Git.

---

## Step 2: Configure PuTTY Session

1. **Open PuTTY**

2. **Configure Connection**:
   - **Host Name (or IP address)**: `52.221.248.235`
   - **Port**: `22`
   - **Connection type**: `SSH`

3. **Set Username**:
   - In left panel, go to **Connection** → **Data**
   - **Auto-login username**: `ubuntu`

4. **Configure SSH Key**:
   - In left panel, go to **Connection** → **SSH** → **Auth**
   - Click **Browse** under "Private key file for authentication"
   - Navigate to where you saved `trading-engine-key.ppk`
   - Select the file and click **Open**

5. **Optional - Configure Window**:
   - Go to **Window** → **Appearance**
   - **Font settings**: Click **Change** to increase font size (recommended: Consolas, 12pt)
   - Go to **Window** → **Selection**
   - Increase **Scrollback lines** to 20000 (for better history)

6. **Save Session**:
   - Go back to **Session** category
   - **Saved Sessions**: Enter name like "Trading Engine Server"
   - Click **Save**

---

## Step 3: Connect to Server

1. **Load your saved session**:
   - Select "Trading Engine Server" from Saved Sessions
   - Click **Load**

2. **Click Open** to connect

3. **First Connection**:
   - You'll see a security alert: "The server's host key is not cached"
   - Click **Yes** to accept and cache the host key

4. **If using passphrase**:
   - Enter your passphrase when prompted
   - Check "Save passphrase" if you want PuTTY to remember it

5. **You should now be connected!**
   - You should see: `ubuntu@ip-xxx-xxx-xxx-xxx:~$`

---

## Step 4: Verify Connection

Once connected, run these commands to verify:

```bash
# Check current user
whoami
# Should output: ubuntu

# Check system info
uname -a

# Check Ubuntu version
lsb_release -a

# Check disk space
df -h

# Check memory
free -h
```

---

## Troubleshooting

### Problem: "Server's host key not cached"
- **Solution**: Click **Yes** to accept the host key (this is normal on first connection)

### Problem: "Permission denied (publickey)"
- **Solution**: 
  - Verify the PEM key was converted correctly
  - Check that the `.ppk` file path is correct in PuTTY settings
  - Make sure you're using the correct username (`ubuntu`)

### Problem: "Network error: Connection refused"
- **Solution**:
  - Verify server IP: `52.221.248.235`
  - Check if server is running
  - Verify port 22 is open
  - Try pinging: `ping 52.221.248.235` (from Windows Command Prompt)

### Problem: "PuTTY window closes immediately"
- **Solution**:
  - Check PuTTY → Connection → Data → Auto-login username is set to `ubuntu`
  - Verify key file path is correct
  - Enable logging: PuTTY → Session → Logging → Enable session logging

---

## Recommended Folder Structure

Create a secure folder for your keys:

```
C:\Users\YourUsername\.ssh\
├── trading-engine-key.ppk    (Your converted key)
└── trading-engine-key.pem    (Original PEM - optional backup)
```

**To create the folder**:
1. Open File Explorer
2. Navigate to `C:\Users\YourUsername\`
3. Create new folder named `.ssh` (if it doesn't exist)
4. Move your PEM file there (optional)
5. Save your `.ppk` file there

---

## Next Steps

After successfully connecting:

1. ✅ **Verify connection works**
2. ✅ **Proceed to Phase 1.2**: Setup SSH Key Authentication for deployment user
3. ✅ **Follow deployment plan**: Continue with Phase 1.3 (Install Essential Packages)

---

## Security Notes

- ⚠️ **Never share your `.ppk` or `.pem` files**
- ⚠️ **Don't commit keys to Git**
- ⚠️ **Keep keys in a secure location**
- ✅ **Consider setting a passphrase on your key**
- ✅ **Use WinSCP with the same key for file transfers**

---

## Quick Reference

**Server Details**:
- IP: `52.221.248.235`
- Username: `ubuntu`
- Port: `22`
- Key Format: `.ppk` (converted from PEM)

**PuTTY Session Name**: Trading Engine Server

**Key File Location**: `C:\Users\YourUsername\.ssh\trading-engine-key.ppk` (recommended)

