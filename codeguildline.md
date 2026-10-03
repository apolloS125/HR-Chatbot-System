# Code Guidelines

Write code so the next person can understand it quickly. Prefer clear, ordinary code over clever shortcuts or extra abstractions.

## General

- Put one statement on a line. Do not compress `if`, `try`, loops, or multiple actions into one line.
- Break long expressions and function calls across lines. Keep lines near 100 characters when practical.
- Use names that explain purpose. Add a short comment only when the reason is not clear from the code.
- Keep functions focused. Extract a helper when it removes real duplication or makes a complex step easier to follow; do not add speculative layers.
- Handle expected failures explicitly. Do not silently swallow errors or expose secrets in logs and responses.
- Reuse the project's existing libraries and patterns. Do not add a dependency or configuration option without a concrete need.

## Python backend

- Use four-space indentation, `snake_case` names, and imports at the top of the file.
- Put multi-step validation and error handling on separate lines with normal blocks.
- Break database filters, updates, and document construction into readable multi-line structures when they get long.
- Add type hints to public functions and values when they clarify the contract; avoid noisy types that merely repeat the implementation.
- Keep async operations visibly ordered. Use transactions and atomic database operations where data integrity requires them.

```python
if not employee:
    raise HTTPException(status_code=404, detail="employee not found")

result = await database.employees.update_one(
    {"_id": employee_code},
    {"$set": {"active": False}},
)
```

## TypeScript and React frontend

- Use two-space indentation, semicolons, and the existing double-quote style.
- Use `camelCase` for values and functions and `PascalCase` for React components and types.
- Give exported functions and shared data types explicit types where they help callers.
- Keep JSX readable; move repeated or stateful UI into a component only when that makes the screen simpler.
- Handle loading, success, and error states clearly. Keep user-facing text understandable and localized consistently with nearby UI.

## Before finishing

- Review the changed code for compressed statements, oversized lines, duplicate logic, and unclear names.
- Run the smallest relevant build or test check and report what passed or could not run.
- Keep the change focused; do not reformat unrelated files.
