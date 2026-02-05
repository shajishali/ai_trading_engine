# Backtesting Test Instructions

## How to Run the Test Script

### Option 1: Using Django Shell (Recommended)

1. **SSH into your server** (via Putty)

2. **Navigate to your project directory:**
   ```bash
   cd /path/to/your/project
   # or
   cd d:\Research Development
   ```

3. **Activate your virtual environment** (if using one):
   ```bash
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

4. **Run Django shell:**
   ```bash
   python manage.py shell
   ```

5. **Copy and paste the entire contents of `test_backtest_simple.py`** into the shell, or run:
   ```python
   exec(open('backend/test_backtest_simple.py').read())
   ```

### Option 2: Run Full Diagnostic Test

```bash
python manage.py shell < backend/test_backtesting.py
```

### Option 3: Direct Python Execution

```bash
python manage.py shell
```

Then copy-paste this code:

```python
import json
from datetime import datetime
from django.test import RequestFactory
from apps.signals.backtesting_api import BacktestAPIView

# Test backtesting
factory = RequestFactory()
request = factory.post(
    '/signals/api/backtests/',
    data=json.dumps({
        'symbol': 'BTC',
        'start_date': '2021-01-01',
        'end_date': '2021-12-31',
        'action': 'backtest'
    }),
    content_type='application/json'
)

api_view = BacktestAPIView()
response = api_view.post(request)
response_data = json.loads(response.content.decode('utf-8'))

print("Success:", response_data.get('success'))
print("Result:", json.dumps(response_data.get('result', {}), indent=2))
```

## What to Look For

The test will show:

1. **Database State:**
   - Are symbols available?
   - Are there existing signals?
   - Is historical market data available?

2. **Signal Generation:**
   - Can signals be generated?
   - How many signals are generated?

3. **Backtest Results:**
   - Total signals count
   - Executed vs Not Opened count
   - Profit vs Loss signals
   - Individual signal details

## Common Issues

### If everything shows "Not Opened":
- Check if historical market data exists
- Check if signals have valid entry/target/stop prices
- Check the `_simulate_single_signal_execution` function logic

### If no signals are generated:
- Check if market data exists for the date range
- Check the strategy service is working
- Verify symbol exists in database

### If API returns error:
- Check the error message
- Verify dates are in correct format (YYYY-MM-DD)
- Check symbol name is correct

## Send the Output

After running the test, copy the entire output and send it for analysis.
