## Code Style Guidelines

### Jupyter-Style Interactive Development
- Use `#%%` cell markers to enable interactive execution in VS Code
- Structure code in logical blocks that can be run independently
- Include intermediate print statements for debugging/verification
- Keep data exploration and transformation visible for step-by-step checking

### Pandas Operations
- **Always use vectorized operations** instead of loops when working with DataFrames
- Prefer: `df['new_col'] = df['col1'] * df['col2']`
- Avoid: `for i in range(len(df)): df.loc[i, 'new_col'] = ...`
- Use `.apply()` with lambda only when vectorization isn't possible
- Chain operations where readable: `df.groupby().agg().reset_index()`

### Simple Formula Style
- **Write calculations as clear, simple formulas** that match business logic
- Use descriptive variable names that match financial terminology
- Examples:
  ```python
  df['gross_profit'] = df['revenue'] - df['cogs']
  df['net_margin'] = df['net_income'] / df['revenue']
  df['roa'] = df['net_income'] / df['total_assets']
  df['loan_growth_qoq'] = df['loan'].pct_change()
  df['provision_coverage'] = df['provision'] / df['npl']
  ```
- Avoid complex nested calculations - break them into intermediate steps:
  ```python
  # Good - clear steps
  df['operating_income'] = df['revenue'] - df['operating_expenses']
  df['ebit'] = df['operating_income'] - df['depreciation']
  df['net_income'] = df['ebit'] - df['interest'] - df['tax']
  
  # Avoid - hard to understand
  df['net_income'] = df['revenue'] - df['operating_expenses'] - df['depreciation'] - df['interest'] - df['tax']
  ```

### Class Design Philosophy
- **Avoid classes unless managing state or encapsulation is essential**
- Prefer simple functions for data transformations
- Use classes only for:
  - Generators that maintain configuration and state (e.g., BulkCommentGenerator)
  - Components that need initialization and multiple related methods
- For single-use operations, use standalone functions

### Testing Approach
- **No edge case testing required** - focus on main functionality
- Assume data inputs are valid and properly formatted
- Handle obvious errors (missing files, API keys) but don't over-engineer
- Trust that data files follow expected schema

### No Emojis in Code
- **Never use emojis in any code files** - keep all code professional and clean
- No emojis in:
  - Comments or docstrings
  - Print statements or log messages
  - Variable names or function names
  - Error messages or success indicators
- Use plain text alternatives:
  - Instead of "✓" or "✅" use "Done" or "Complete"
  - Instead of "✗" or "❌" use "Failed" or "Error"
  - Instead of "📊" use "[Plot]" or "Chart:"
  - Instead of "⚠️" use "Warning:" or "Alert:"

### Code Organization Examples
```python
#%% Load and prepare data
df = pd.read_csv('data.csv')
print(f"Loaded {len(df)} rows")

#%% Transform data - vectorized approach
df['quarter_numeric'] = df['Date_Quarter'].apply(quarter_to_numeric)
df['growth'] = df.groupby('TICKER')['value'].pct_change()

#%% Generate results
results = df[df['quarter_numeric'] > 20240].groupby('TICKER').agg({
    'growth': 'mean',
    'value': 'last'
})
print(results.head())
```