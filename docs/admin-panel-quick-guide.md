# Admin Panel Quick Guide - Phase 1 Features

## Accessing the Admin Panel

1. Start the Django server:
   ```bash
   python manage.py runserver
   ```

2. Navigate to: `http://localhost:8000/admin/`

3. Login with your admin credentials

## Enhanced Admin Sections

### 1. **Users** (AUTHENTICATION AND AUTHORIZATION → Users)

**Enhanced Features:**
- ✅ **Subscription Status** column - Shows subscription status with color coding
- ✅ **Signals Used** column - Shows daily signal usage with limits
- ✅ **Last Login** column - Shows relative time (e.g., "2h ago", "3d ago")
- ✅ **Account Age** column - Shows how long the account has been active
- ✅ **Inline Views** - See UserProfile and Payment history directly on user detail page
- ✅ **Custom Filters** - Filter by subscription status and plan
- ✅ **Bulk Actions** - Activate/Deactivate users, Export user list

**How to Use:**
- Click on "Users" in the sidebar
- View the enhanced list with all subscription information
- Click on any user to see their profile and payment history inline
- Use filters on the right sidebar to find specific users
- Select multiple users and use bulk actions from the dropdown

---

### 2. **Subscriptions & Payments** Section

This section contains all subscription-related models:

#### **Subscription Plans**
- View all subscription plans
- See **user count** per plan (how many users are subscribed)
- See **revenue** per plan
- Edit plan features and pricing

#### **User Profiles**
- View all user profiles with subscription information
- **Enhanced List Display:**
  - Subscription status with color coding
  - Signal usage with percentage
  - Subscription expiry with time remaining
- **Custom Filters:**
  - Subscription Status (Active, Trial, Expired, Inactive, Cancelled)
  - Expires In (Today, This Week, This Month, Already Expired)
- **Bulk Actions:**
  - Extend trial by 7/30 days
  - Activate/Cancel subscriptions
  - Upgrade to Pro / Downgrade to Basic
- **Detail View:**
  - Subscription timeline visualization
  - Links to payment history and subscription history

#### **Payments**
- View all payment records
- **Enhanced List Display:**
  - Formatted amount display
  - Color-coded status indicators
  - Payment provider links
- **Custom Filters:**
  - Payment Status (Completed, Pending, Failed, Refunded)
  - Payment Date (Today, This Week, This Month, This Year)
- **Bulk Actions:**
  - Mark as completed/failed/refunded
- **Analytics:**
  - Revenue contribution per payment

#### **Subscription Histories**
- View all subscription changes (upgrades, downgrades, cancellations)
- Track subscription lifecycle

#### **Email Verification Tokens**
- Manage email verification tokens
- View token status and expiry

---

## Color Coding Guide

### Subscription Status Colors:
- 🟢 **Green**: Active subscriptions
- 🔵 **Blue**: Trial users
- ⚪ **Gray**: Inactive
- 🔴 **Red**: Cancelled
- 🟠 **Orange**: Expired or expiring soon

### Payment Status Colors:
- 🟢 **Green**: Completed
- 🟠 **Orange**: Pending
- 🔴 **Red**: Failed
- ⚪ **Gray**: Refunded

### Signal Usage Colors:
- 🟢 **Green**: < 70% of limit used
- 🟠 **Orange**: 70-90% of limit used
- 🔴 **Red**: > 90% of limit used

---

## Quick Actions

### To Manage a User's Subscription:
1. Go to **Users** → Click on the user
2. Scroll to the **Profile** inline section
3. Update subscription plan, status, or dates
4. Save changes

### To View User's Payment History:
1. Go to **Users** → Click on the user
2. Scroll to the **Payment** inline section
3. Or go to **User Profiles** → Click on the profile → Click "View X payment(s)" link

### To Extend Multiple Trials:
1. Go to **User Profiles**
2. Use the "Subscription Status" filter to find "Trial Users"
3. Select multiple profiles
4. Choose "Extend trial by 7 days" or "Extend trial by 30 days" from Actions dropdown
5. Click "Go"

### To View Subscription Statistics:
1. Go to **Subscription Plans**
2. Click on any plan to see:
   - Number of users on that plan
   - Total revenue from that plan

---

## Tips

1. **Use Filters**: The custom filters make it easy to find specific users or subscriptions
2. **Bulk Operations**: Select multiple items and use bulk actions for efficiency
3. **Inline Views**: View related information without leaving the current page
4. **Color Coding**: Quickly identify status at a glance using the color indicators
5. **Links**: Click on links in detail views to navigate to related records

---

## Troubleshooting

**If you don't see the subscription models:**
- Make sure the server is restarted after the changes
- Check that you're logged in as a superuser
- Verify the models are registered: They should appear under "SUBSCRIPTIONS & PAYMENTS" section

**If filters don't work:**
- Clear your browser cache
- Make sure the server was restarted after adding the filters

**If bulk actions don't work:**
- Make sure you've selected at least one item
- Check that you have the necessary permissions

---

## Next Steps

Phase 2 will add:
- Signal showcase with time-based filtering
- Signal performance tracking
- Advanced visualizations
- Export functionality

Enjoy your enhanced admin panel! 🎉




