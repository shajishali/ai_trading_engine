# Phase 0: Pre-Deployment Preparation - Progress Tracker

**Status**: 🟡 In Progress  
**Started**: 2025-12-03

---

## Phase 0.1: PuTTY and PuTTYgen Setup

### Step 1: Install PuTTY and PuTTYgen
- [x] PuTTY downloaded and installed ✅
- [x] PuTTYgen available (usually included with PuTTY) ✅
- [ ] WinSCP downloaded and installed (recommended) - Optional

**Status**: ✅ Completed

---

## Phase 0.2: Server Access Setup

### Step 1: Convert PEM Key to PuTTY Format
- [x] PEM key located: `id_2025_11_28_intern_4.pem` in Downloads folder ✅
- [ ] PuTTYgen opened
- [ ] PEM key imported into PuTTYgen
- [ ] Key saved as `.ppk` format
- [ ] Key saved to secure location (recommended: `C:\Users\YourUsername\.ssh\`)

**Status**: 🟡 In Progress - Following step-by-step instructions

### Step 2: Configure PuTTY Session
- [ ] PuTTY opened
- [ ] Server IP configured: `52.221.248.235`
- [ ] Port set to: `22`
- [ ] Username set to: `ubuntu`
- [ ] Private key file configured (`.ppk` file)
- [ ] Session saved as "Trading Engine Server"

**Status**: ⏳ Waiting for user to configure PuTTY

### Step 3: Test Connection
- [ ] Successfully connected to server
- [ ] Host key accepted
- [ ] Can run commands in PuTTY terminal
- [ ] Verified Ubuntu version

**Status**: ⏳ Waiting for connection test

---

## Phase 0.3: Server Information Gathering

### Server Details
- [x] Server IP: `52.221.248.235` ✅
- [x] Username: `ubuntu` ✅
- [ ] Ubuntu version confirmed (run: `lsb_release -a`)
- [ ] Server accessible (ping test successful)
- [ ] Firewall ports checked (22, 80, 443, 8000)

**Status**: ⏳ Waiting for connection to gather info

---

## Phase 0.4: Local Environment Preparation

### Git Repository
- [ ] All code committed to Git
- [ ] No uncommitted changes
- [ ] Repository is clean

**Status**: ⏳ Need to check

### Environment Variables
- [x] `env.production.template` exists ✅
- [ ] Production `.env` file prepared (NOT committed to Git)
- [ ] All required variables documented

**Status**: ⏳ Need to prepare

### Local Testing
- [ ] Application tested locally
- [ ] All features working
- [ ] Database migrations tested

**Status**: ⏳ Need to verify

---

## Phase 0.5: Resource Planning

### Storage Requirements
- [ ] Database size estimated
- [ ] Log files space calculated
- [ ] Static files size estimated
- [ ] Total storage requirement calculated

**Status**: ⏳ Need to calculate

### Memory Planning
- [ ] 2GB RAM allocation planned
- [ ] Service memory requirements reviewed
- [ ] Swap space planned if needed

**Status**: ⏳ Need to review

---

## Next Steps

1. **Install PuTTY/PuTTYgen** (if not already installed)
2. **Convert PEM key to .ppk format**
3. **Configure PuTTY and test connection**
4. **Gather server information**
5. **Prepare local environment**
6. **Complete resource planning**

---

## Notes

- Server IP: 52.221.248.235
- Username: ubuntu
- Key file: PEM (needs conversion to .ppk)

