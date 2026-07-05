---
name: padrino-finance
description: Finance manager for Padrino Digital. Transaction CRUD (income/expense/transfer/adjustment), budget tracking with warning thresholds, debt monitoring, savings goal tracking, business area separation, CSV export, and 7 critical finance rules — with correction audit trail via reversal entries.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    tags: [padrino, finance, transactions, budgets, savings, debts, money, reporting]
    related_skills: [padrino-soul, padrino-inbox, padrino-review]
    commands: [/gastos, /ingresos, /finanzas, /presupuesto, /ahorro, /deudas]
    writes_to: [padrino.db]
    reads_from: [padrino.db]
---

# padrino-finance — Finance Manager

## Purpose

Record financial transactions, track budgets with warning thresholds, manage
savings goals, and monitor debts — with strict rules against moving money,
connecting to banks (MVP), or giving financial advice as certainty. All
financial mutations require explicit approval.

## When to Use

- Automatically: when `padrino-inbox` classifies a message as `expense` or `income`
- Automatically: during daily/weekly/monthly reviews for financial summaries
- Manually: all `/finanzas`, `/gastos`, `/ingresos`, `/presupuesto`, `/ahorro`,
  `/deudas` commands

---

## 7 Critical Rules (NON-NEGOTIABLE)

These rules are the foundation. Violations are REFUSED with explanation, not
silently ignored.

### Rule 1: Never move money between real accounts

The system does NOT execute transfers between real bank accounts, MercadoPago,
or any financial institution. It can RECORD transfers for tracking purposes,
but the user must execute the actual movement themselves.

```
User: "Pasame $10,000 de la cuenta del banco a MercadoPago"

Padrino: "No muevo plata entre cuentas reales. Esto lo tenés que hacer vos
         desde la app del banco o MercadoPago. Si querés, lo registro como
         transferencia después de que lo hagas: 'Transferí $10,000 de banco
         a MercadoPago'."
```

### Rule 2: Never connect to banks (MVP)

No API integrations with financial institutions. No screen scraping. No
bank credentials stored. This is a manual-entry system in MVP.

```
User: "Conectate a mi home banking"

Padrino: "No me conecto a bancos ni home banking. Este es un sistema de
         registro manual. Cargame los datos vos y yo los organizo."
```

### Rule 3: Don't assume business income = personal profit

When the user reports business income, the system warns against conflating
it with personal profit before expenses, taxes, and reinvestment are accounted for.

```
User: "Cobré $200,000 de Nexios"

Padrino: "Registrado: ingreso de $200,000 ARS (Nexios).
         ⚠️ Recordá: esto es ingreso bruto del negocio, no ganancia personal.
         ¿Querés registrar también los gastos asociados de Nexios este mes?"
```

### Rule 4: Don't mix transfers with income/expense

Transfers between accounts are NOT income or expense. They're just money
moving. Use `type='transfer'` for account-to-account movements within the
user's own ecosystem.

| Movement | Type | Meaning |
|----------|------|---------|
| Salary, client payment, sale | `income` | Money entering your ecosystem |
| Purchase, bill, payment to third party | `expense` | Money leaving your ecosystem |
| Moving money between your accounts | `transfer` | Rebalancing, no net change |
| Correcting a past error | `adjustment` | Fixing a mistake |

### Rule 5: Keep original currency

Store transactions in the currency they occurred in. Convert to ARS only for
reports, and always store the conversion metadata:

```
original_currency: 'USD'
original_amount: 100.00
conversion_rate: 1250.50
conversion_source: 'dolarhoy.com'
conversion_date: '2026-07-05'
amount: 125050.00        -- converted to ARS
currency: 'ARS'
```

When the user reports a non-ARS transaction:

```
User: "Gasté USD 50 en Spotify"

Padrino: "¿A qué tipo de cambio querés convertir? Necesito:
         1. Tasa (ej: 1250)
         2. Fuente (ej: dolarhoy.com, BCRA, tarjeta)
         3. Fecha de la conversión

         Mientras tanto, lo registro como USD 50."
```

### Rule 6: Never give financial advice as certainty

All projections, estimates, and analyses MUST carry a disclaimer. The system
presents data, not recommendations.

Required disclaimer on any projection:
```
⚠️ Esto NO es asesoramiento financiero. Son números basados en tus datos
registrados. Las proyecciones son estimaciones, no certezas.
```

### Rule 7: Allow corrections with audit trail

Corrections never overwrite original data. Instead:

1. Create a **reversal entry** (negates the original with `correction_id` pointing to it)
2. Create a **new correct entry** (also with `correction_id` linking to the original)
3. Log the correction in `audit_log`

```
Original:    id=100, type=expense, amount=10000, description="Supermercado"
Reversal:    id=101, type=expense, amount=-10000, correction_id=100
Correction:  id=102, type=expense, amount=15000, correction_id=100,
             description="Supermercado (corregido: eran $15,000)"
```

Correction flow:

```
User: "El gasto del supermercado fue $15,000, no $10,000"

Padrino: "Corrijo:
          • Original: $10,000 Supermercado (05/07) — ANULADO
          • Nuevo: $15,000 Supermercado (05/07) — CORREGIDO
          
          ¿Confirmás la corrección?"

→ Approval gate → INSERT reversal + new entry with correction_id
→ INSERT INTO audit_log (action='CORRECTION', target='transactions', details=...)
```

---

## Transaction CRUD

### Transaction types

| Type | When to use | Amount sign |
|------|-------------|-------------|
| `income` | Money received: salary, client payment, sale, gift | Positive |
| `expense` | Money spent: purchase, bill, payment to third party | Positive (amount is the cost) |
| `transfer` | Moving money between own accounts | Positive (amount is what moved) |
| `adjustment` | Correcting a past error (reversal entries use negative amounts) | Positive or negative |

### Recording a transaction

```
User: "Gasté $15,000 en nafta para el Rastrojero, efectivo"

Step 1 — Extract fields:
  type: expense
  amount: 15000
  currency: ARS
  category: combustible
  business_area: Rastrojero
  payment_method: efectivo
  date: today (unless specified)
  description: "Nafta Rastrojero"

Step 2 — Check for missing required fields:
  - amount? ✅ 15000
  - currency? ✅ ARS (default)
  - category? ✅ combustible
  - date? ✅ today (default)

Step 3 — Present for approval:
  Padrino: "Registro: Gasto · $15,000 ARS · Combustible · Rastrojero · Efectivo · 05/07
           ¿Confirmás?"

Step 4 — On approval, INSERT:
  INSERT INTO transactions (type, amount, currency, category, business_area,
    payment_method, date, description, approved_by, approved_at)
  VALUES ('expense', 15000, 'ARS', 'combustible', 'Rastrojero',
    'efectivo', '2026-07-05', 'Nafta Rastrojero', 'user', datetime('now'));

Step 5 — Check budget:
  SELECT limit_amount, warning_percent FROM budgets
  WHERE category = 'combustible' AND period = 'monthly';

  If budget exists and current spending ≥ warning_percent:
    Padrino: "⚠️ Combustible: ${spent}/${limit} ({pct}%)"
```

### Missing field handling

| Missing field | Action |
|---------------|--------|
| `amount` | "¿Cuánto fue?" |
| `currency` | Default to ARS, but ask if the context suggests otherwise |
| `category` | "¿Qué categoría? (comida, nafta, servicios, etc.)" |
| `date` | Default to today: "¿Fue hoy? ¿O de otro día?" |
| `business_area` | Infer from context (project mentions, keywords). If ambiguous: "¿Es personal, de Nexios, del Rastrojero...?" |
| `payment_method` | Optional. Only ask if it matters for the user's tracking |

### Approval gate

ALL transaction mutations (INSERT, UPDATE, DELETE) require approval. The
approval message shows:

```
¿Confirmás este registro?

  Tipo:       Gasto
  Monto:      $15,000 ARS
  Categoría:  Combustible
  Área:       Rastrojero
  Fecha:      2026-07-05
  Método:     Efectivo
  Descripción: Nafta Rastrojero

[Confirmar] [Cancelar]
```

After approval, `approved_by` is set to `'user'` and `approved_at` is set.

---

## Budget Management

### Budget data model

```sql
-- Example budgets
INSERT INTO budgets (category, period, limit_amount, currency, warning_percent, business_area)
VALUES
  ('comida', 'monthly', 100000, 'ARS', 80, 'personal'),
  ('combustible', 'monthly', 30000, 'ARS', 80, 'Rastrojero'),
  ('servicios', 'monthly', 25000, 'ARS', 80, 'personal'),
  ('salidas', 'monthly', 50000, 'ARS', 80, 'personal');
```

### Warning system

| Threshold | Action |
|-----------|--------|
| < warning_percent | Normal — no notification |
| ≥ warning_percent, < 100% | ⚠️ Warning: "Categoría {X}: ${spent}/${limit} ({pct}%) — estás por encima del umbral de alerta" |
| ≥ 100%, < 120% | 🔴 Exceeded: "Presupuesto {X} excedido: ${spent}/${limit} ({pct}%)" |
| ≥ 120% | 🚨 Critical: "Presupuesto {X} severamente excedido ({pct}%). ¿Revisamos?" |

### Budget check (on every expense INSERT)

```sql
SELECT b.category, b.limit_amount, b.warning_percent,
       COALESCE(SUM(t.amount), 0) AS spent_this_period
FROM budgets b
LEFT JOIN transactions t ON t.category = b.category
    AND t.type = 'expense'
    AND t.date BETWEEN date('now', 'start of month') AND date('now')
    AND t.deleted_at IS NULL
WHERE b.deleted_at IS NULL AND b.active = 1
  AND b.category = '{new_transaction_category}'
GROUP BY b.id;
```

If `spent_this_period + new_amount ≥ limit_amount * warning_percent / 100`,
trigger the appropriate warning.

### Creating a budget

```
/presupuesto crear "Servicios" --limite 25000 --periodo mensual --alerta 80 --area personal

Padrino: "Presupuesto creado: Servicios · $25,000/mes · Alerta al 80% ($20,000)"
```

### Listing budgets

```
/presupuesto

→ Muestra todos los presupuestos activos con estado actual:

| Categoría    | Límite    | Gastado   | %     | Estado |
|--------------|-----------|-----------|-------|--------|
| Comida       | $100,000  | $45,000   | 45%   | ✅     |
| Combustible  | $30,000   | $28,000   | 93%   | ⚠️     |
| Servicios    | $25,000   | $12,500   | 50%   | ✅     |
| Salidas      | $50,000   | $55,000   | 110%  | 🔴     |
```

---

## Savings Goals

### Goal tracking

```sql
SELECT name, target_amount, current_amount,
       ROUND(current_amount / target_amount * 100, 1) AS progress_pct,
       deadline,
       CASE
         WHEN current_amount >= target_amount THEN 'completed'
         WHEN deadline IS NOT NULL AND date(deadline) < date('now') THEN 'overdue'
         WHEN ROUND(current_amount / target_amount * 100) >= 75 THEN 'on_track'
         ELSE 'in_progress'
       END AS status_label
FROM savings_goals
WHERE status = 'active' AND deleted_at IS NULL;
```

### Recording progress

```
/ahorro avanzar 1 --monto 25000

Padrino: "Meta 'Fondo emergencia': $175,000/$500,000 (35%).
         Te faltan $325,000. Al ritmo actual de $25,000/mes,
         llegarías en ~13 meses (enero 2027)."
```

### Progress alerts

```
⚠️ Meta 'Viaje' — $50,000/$300,000 (17%)
   Vence en 3 meses (2026-10-01).
   Necesitás $83,333/mes para llegar. Tu aporte actual es $10,000/mes.
   ⚠️ Esto NO es asesoramiento financiero. Son números basados en tus datos.
```

---

## Debt Tracking

### Debt data model

Each debt tracks:
- `total_amount` — original loan amount
- `remaining_amount` — what's left to pay
- `minimum_payment` — the minimum due each period (stored in `notes` convention or separate tracking)

### Debt status transitions

```
active → paid (remaining_amount reaches 0)
active → defaulted (missed payments beyond threshold)
active → negotiating (renegotiating terms)
```

### Payment recording

```
User: "Pagué $15,000 del préstamo del auto"

Padrino: "Registro: Pago de deuda 'Préstamo auto' · $15,000 ARS.
         Restante: $30,000/$200,000 (85% pagado).
         ¿Confirmás?"

→ UPDATE debts SET remaining_amount = remaining_amount - 15000,
    updated_at = datetime('now')
    WHERE id = {debt_id}
→ INSERT INTO transactions (type='expense', category='deuda', ...)
→ INSERT INTO audit_log (action='DEBT_PAYMENT', target='debts', ...)
```

### Upcoming payments

```
/deudas proximos

→ Muestra deudas con vencimientos en los próximos 30 días:

| Deuda            | Cuota      | Vence      | Restante   |
|------------------|------------|------------|------------|
| Préstamo auto    | $15,000    | 2026-07-10 | $30,000    |
| Tarjeta Visa     | $45,000    | 2026-07-15 | $45,000    |
```

---

## Business Area Separation

All transactions are tagged with `business_area` for separation:

| Area | Description |
|------|-------------|
| `personal` | Personal expenses/income not tied to any business |
| `Ascend` | Ascend project income/expenses |
| `fletes` | Fletes/moving service income/expenses |
| `Nexios` | Nexios software income/expenses |
| `Rastrojero` | Rastrojero vehicle project expenses |
| `home-gym` | Home gym project expenses |
| `otros` | Any other business/venture |

### Area reports

```
/finanzas area Nexios

→ "Nexios — Julio 2026:

   Ingresos: $200,000 (1 transacción)
   Gastos: $35,000 (3 transacciones)
     • Hosting: $15,000
     • Dominio: $5,000
     • Herramientas: $15,000
   
   Neto: +$165,000
   
   ⚠️ Recordá: esto es bruto del negocio, no ganancia personal.
   Impuestos y aportes no están descontados."
```

---

## Reports

### Monthly report

```
/finanzas --mes 7 --año 2026

→ Reporte completo con:
  • Resumen: ingresos, gastos, balance
  • Por categoría (top 10 categorías de gasto)
  • Por área de negocio
  • Presupuestos vs. real
  • Ahorros: progreso del mes
  • Deudas: pagos del mes, saldo actual
  • ⚠️ Disclaimer obligatorio
```

### Spending by category

```
/finanzas categorias --mes 7

| Categoría    | Gastos     | % del total |
|--------------|------------|-------------|
| Comida       | $45,000    | 35%         |
| Combustible  | $28,000    | 22%         |
| Servicios    | $25,000    | 19%         |
| Salidas      | $18,000    | 14%         |
| Otros        | $13,000    | 10%         |
| **Total**    | **$129,000** | **100%**  |
```

---

## CSV Export

### Export command

```
/finanzas exportar --mes 7 --año 2026 --formato csv

→ Generates a CSV file with all transactions for the month:

  id,type,amount,currency,category,business_area,payment_method,date,description
  1,income,200000,ARS,servicios,Nexios,transferencia,2026-07-01,"Pago cliente Nexios"
  2,expense,15000,ARS,combustible,Rastrojero,efectivo,2026-07-05,"Nafta Rastrojero"
  ...

→ File saved to: /srv/padrino/data/exports/finanzas_2026-07.csv
→ ⚠️ Este archivo contiene datos financieros personales. Protegelo.
```

### Export format

- UTF-8 with BOM (for Excel compatibility)
- Comma-separated, strings quoted with double quotes
- Date format: YYYY-MM-DD
- Amount format: numeric, no thousands separator, decimal point
- First row: headers

### Export filters

```
/finanzas exportar --desde 2026-01-01 --hasta 2026-07-05
/finanzas exportar --area Nexios
/finanzas exportar --categoria combustible
/finanzas exportar --tipo expense
```

---

## Projections and Estimates

When the user asks for projections:

```
User: "¿Cuánto voy a gastar este mes?"

Padrino: "⚠️ Esto NO es asesoramiento financiero. Son números basados
         en tus datos registrados.

         Proyección estimada: ~$145,000 ARS
         • Gasto actual (5 días): $24,000
         • Promedio diario: $4,800
         • Días restantes: 26
         • Proyección: $24,000 + (26 × $4,800) = ~$148,800

         Metodología: extrapolación lineal del gasto diario promedio.
         Limitación: no considera gastos fijos del 10 y 25.

         ¿Querés que ajuste la proyección con tus gastos fijos conocidos?"
```

Projections always include:
1. ⚠️ Disclaimer
2. Methodology (how the number was calculated)
3. Limitations (what the model doesn't account for)
4. Offer to refine

---

## Commands Reference

### `/gastos` — Record an expense (shortcut)

```
/gastos 15000 combustible Rastrojero efectivo "Nafta"
→ Direct expense recording (skips inbox routing)
→ Still requires approval gate
```

### `/ingresos` — Record income (shortcut)

```
/ingresos 200000 servicios Nexios transferencia "Pago cliente"
→ Direct income recording
→ Still requires approval gate
```

### `/finanzas` — Finance hub

| Sub-command | Action |
|-------------|--------|
| `/finanzas` | Current month summary (income, expenses, balance by area) |
| `/finanzas --mes <N> --año <YYYY>` | Specified month summary |
| `/finanzas categorias` | Spending breakdown by category |
| `/finanzas areas` | Income/expense breakdown by business area |
| `/finanzas exportar` | Export transactions to CSV |
| `/finanzas corregir <id>` | Initiate transaction correction flow |

### `/presupuesto` — Budget management

| Sub-command | Action |
|-------------|--------|
| `/presupuesto` | List all budgets with current status |
| `/presupuesto crear <name>` | Create a new budget |
| `/presupuesto ver <name>` | Detail view of one budget |
| `/presupuesto editar <name>` | Edit budget properties |
| `/presupuesto eliminar <name>` | Delete budget (soft-delete) |

### `/ahorro` — Savings goals

| Sub-command | Action |
|-------------|--------|
| `/ahorro` | List all savings goals with progress |
| `/ahorro crear <name> --objetivo <n> --fecha <YYYY-MM-DD>` | Create savings goal |
| `/ahorro avanzar <id> --monto <n>` | Record progress toward goal |
| `/ahorro ver <id>` | Detail view of a savings goal |

### `/deudas` — Debt tracking

| Sub-command | Action |
|-------------|--------|
| `/deudas` | List all active debts |
| `/deudas crear <name>` | Create a debt record |
| `/deudas pagar <id> --monto <n>` | Record a payment |
| `/deudas ver <id>` | Detail view of a debt |
| `/deudas proximos` | Upcoming payments in the next 30 days |

---

## Cross-Skill Contract

### Input from padrino-inbox (classification = expense or income)

```json
{
  "category": "expense",
  "content": "Gasté $15,000 en nafta para el Rastrojero, efectivo",
  "extracted": {
    "type": "expense",
    "amount": 15000,
    "currency": "ARS",
    "category": "combustible",
    "business_area": "Rastrojero",
    "payment_method": "efectivo",
    "date": "2026-07-05"
  }
}
```

### Approval gate interaction with padrino-soul

Before any write:
```json
{
  "approval_required": true,
  "action": "INSERT transactions",
  "summary": "Gasto · $15,000 ARS · Combustible · Rastrojero · Efectivo",
  "details": { "type": "expense", "amount": 15000, ... }
}
```

### Events emitted to other skills

| Event | Consumer | When |
|-------|----------|------|
| `finance.transaction_created(id, type, amount)` | padrino-review | Any new transaction |
| `finance.budget_warning(category, pct, limit)` | padrino-review | Budget threshold crossed |
| `finance.budget_exceeded(category, pct, limit)` | padrino-review | Budget 100%+ exceeded |
| `finance.savings_milestone(goal_id, pct)` | padrino-review | Savings goal hits 25/50/75/100% |
| `finance.debt_paid(debt_id, remaining)` | padrino-review | Debt payment recorded |
| `finance.correction_made(original_id, new_id)` | padrino-review | Transaction corrected |

### Database writes

- `transactions` — INSERT (with approval), UPDATE (corrections only)
- `budgets` — INSERT, UPDATE, soft-delete
- `savings_goals` — INSERT, UPDATE (current_amount)
- `debts` — INSERT, UPDATE (remaining_amount)
- `audit_log` — auto-triggered on transactions INSERT/UPDATE, plus manual entries for corrections

---

## Privacy Note

- Financial data is the most sensitive category in `padrino.db`. The database
  file must have 600 permissions at all times
- CSV exports contain raw financial data — the user is warned about file
  protection on every export
- Never include financial amounts or account details in Telegram messages that
  could be screenshotted without the user's awareness — offer to send sensitive
  summaries as ephemeral or private messages when the context warrants
- The 7 critical rules (especially Rule 1: never move money, Rule 2: never
  connect to banks) are security boundaries, not just conventions
- All financial projections carry the mandatory disclaimer: "Esto NO es
  asesoramiento financiero"
