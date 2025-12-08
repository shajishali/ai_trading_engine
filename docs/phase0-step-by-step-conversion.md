# Phase 0.1: Convert PEM Key to PuTTY Format - Step by Step

**PEM File**: `id_2025_11_28_intern_4.pem`  
**Location**: Downloads folder  
**Target**: Convert to `.ppk` format for PuTTY

---

## Step-by-Step Instructions

### Step 1: Open PuTTYgen

1. **Press Windows Key** on your keyboard
2. **Type**: `puttygen` (or search for "PuTTYgen")
3. **Click** on "PuTTYgen" application
4. PuTTYgen window should open

**✅ Check**: You should see a window with:
- "PuTTY Key Generator" title
- A large blank area
- Buttons: "Generate", "Load", "Save public key", "Save private key"

---

### Step 2: Import Your PEM Key

1. **Click** the **"Load"** button (or go to **Conversions** → **Import key**)
2. **File dialog opens** - Navigate to your **Downloads** folder
3. **Important**: In the file type dropdown (bottom right), select **"All Files (*.*)"** 
   - PEM files might not show by default, so select "All Files"
4. **Find and select**: `id_2025_11_28_intern_4.pem`
5. **Click** "Open"

**✅ Check**: 
- You should see key information appear in PuTTYgen
- The large text area should show "Public key for pasting into OpenSSH authorized_keys file"
- Key type should show (usually RSA or EC)

---

### Step 3: (Optional) Set Key Comment

1. In the **"Key comment"** field, you can add:
   - `trading-engine-production` or
   - `52.221.248.235` (server IP)
2. This helps identify the key later

**Note**: This is optional but recommended for organization.

---

### Step 4: (Optional) Set Passphrase

**Recommended for Security:**

1. In **"Key passphrase"** field, enter a strong password
2. In **"Confirm passphrase"** field, enter the same password
3. **Remember this passphrase!** You'll need it each time you connect

**Note**: 
- If you set a passphrase, you'll be asked for it every time you connect
- If you leave it blank, the key will work without a password (less secure but more convenient)

**Your choice**: Do you want to set a passphrase? (Yes/No)

---

### Step 5: Save the Private Key (.ppk file)

1. **Click** the **"Save private key"** button
2. **Security Warning**: If you didn't set a passphrase, you'll see:
   - "Are you sure you want to save this key without a passphrase?"
   - Click **"Yes"** (if you chose not to use a passphrase)
3. **Save dialog opens**

**Choose Save Location:**

**Recommended**: Create a `.ssh` folder in your user directory

1. **Navigate to**: `C:\Users\YourUsername\` (replace YourUsername with your actual Windows username)
2. **Create folder** (if it doesn't exist):
   - Click "New Folder" button
   - Name it: `.ssh`
   - Press Enter
3. **Enter filename**: `trading-engine-key.ppk`
4. **Click** "Save"

**Alternative Location**: You can save it anywhere secure, like:
- `C:\Users\YourUsername\Documents\Keys\trading-engine-key.ppk`
- Or keep it in Downloads (less secure but easier)

**✅ Check**: 
- File should be saved as `trading-engine-key.ppk`
- Remember where you saved it!

---

### Step 6: Verify the Key File

1. **Navigate** to where you saved the `.ppk` file
2. **Check** that the file exists and has `.ppk` extension
3. **File size** should be similar to your original PEM file

**✅ Success**: You now have `trading-engine-key.ppk` ready to use!

---

## What's Next?

After saving the `.ppk` file, we'll:
1. Configure PuTTY with your server details
2. Test the connection
3. Move to Phase 0.2

---

## Troubleshooting

### Problem: "PuTTYgen: Couldn't load private key"
- **Solution**: Make sure you selected "All Files (*.*)" in the file dialog
- Try again, ensuring you select the PEM file

### Problem: "File not found"
- **Solution**: Check the exact filename: `id_2025_11_28_intern_4.pem`
- Make sure it's in your Downloads folder

### Problem: "Invalid key format"
- **Solution**: The PEM file might be corrupted. Contact your supervisor for a new key.

---

## Quick Checklist

- [ ] PuTTYgen opened
- [ ] PEM key imported successfully
- [ ] Key comment set (optional)
- [ ] Passphrase set (optional but recommended)
- [ ] Private key saved as `.ppk` file
- [ ] Remembered where the `.ppk` file is saved

**Ready for next step?** Let me know when you've completed the conversion!

