#!/bin/bash
# Diagnostic script to find the source of WSL/bash initialization errors

echo "=== Checking for problematic shell initialization files ==="
echo ""

# Check common shell files
echo "1. Checking ~/.bashrc for awk/base64/printf issues..."
if [ -f ~/.bashrc ]; then
    grep -n "awk\|base64\|printf.*var_name\|builtin.*printf" ~/.bashrc 2>/dev/null || echo "  No issues found in .bashrc"
else
    echo "  ~/.bashrc not found"
fi
echo ""

echo "2. Checking ~/.bash_profile..."
if [ -f ~/.bash_profile ]; then
    grep -n "awk\|base64\|printf.*var_name\|builtin.*printf" ~/.bash_profile 2>/dev/null || echo "  No issues found in .bash_profile"
else
    echo "  ~/.bash_profile not found"
fi
echo ""

echo "3. Checking ~/.bash_aliases..."
if [ -f ~/.bash_aliases ]; then
    grep -n "awk\|base64\|printf.*var_name\|builtin.*printf" ~/.bash_aliases 2>/dev/null || echo "  No issues found in .bash_aliases"
else
    echo "  ~/.bash_aliases not found"
fi
echo ""

echo "4. Checking ~/.profile..."
if [ -f ~/.profile ]; then
    grep -n "awk\|base64\|printf.*var_name\|builtin.*printf" ~/.profile 2>/dev/null || echo "  No issues found in .profile"
else
    echo "  ~/.profile not found"
fi
echo ""

echo "5. Checking for shell functions with printf..."
if [ -f ~/.bashrc ]; then
    awk '/^[[:space:]]*[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*\([[:space:]]*\)[[:space:]]*\{/,/^[[:space:]]*\}/' ~/.bashrc | grep -B2 -A10 "printf\|var_name" || echo "  No problematic functions found"
fi
echo ""

echo "6. Checking system-wide files..."
if [ -f /etc/bash.bashrc ]; then
    echo "  Checking /etc/bash.bashrc..."
    grep -n "awk\|base64\|printf.*var_name\|builtin.*printf" /etc/bash.bashrc 2>/dev/null | head -5 || echo "    No issues found"
fi
echo ""

echo "=== Recommendations ==="
echo "1. To temporarily bypass shell initialization, run: bash --norc --noprofile"
echo "2. To test if .bashrc is the issue, rename it: mv ~/.bashrc ~/.bashrc.backup"
echo "3. Check for shell prompt themes (oh-my-bash, powerline, etc.) that might be causing issues"
echo "4. The systemd error is harmless and can be ignored if you're not using systemd in WSL"

