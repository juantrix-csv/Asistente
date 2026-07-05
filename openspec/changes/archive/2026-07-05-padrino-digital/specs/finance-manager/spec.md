# finance-manager Specification

## Purpose

Record transactions, track budgets, manage savings goals, and monitor debts — with strict rules against moving money, connecting to banks (MVP), or giving financial advice as certainty. All financial mutations require explicit approval.

## Requirements

### Requirement: Transaction Recording with Full Metadata

Every transaction MUST record: type (income, expense, transfer, adjustment), amount, currency, category, account, business_area (personal, Ascend, fletes, Nexios, Rastrojero, home-gym, otros), payment_method, date, description, and recurring flag. Missing amount, currency, or category SHALL trigger a confirmation request before the transaction is saved.

#### Scenario: Record a complete expense

- GIVEN the user says "Gasté $15,000 en nafta para el Rastrojero, efectivo"
- WHEN the system processes this
- THEN a transaction SHALL be created with type=expense, amount=15000, currency=ARS, category=combustible, business_area=rastrojero, payment_method=efectivo
- AND SHALL present the full record for confirmation before saving

#### Scenario: Missing amount triggers confirmation request

- GIVEN the user says "Pagué la luz"
- WHEN the system processes this
- THEN it SHALL detect missing amount
- AND SHALL ask: "¿Cuánto pagaste de luz?"
- AND SHALL NOT save the transaction until the amount is provided

#### Scenario: Recurring transaction flag

- GIVEN the user says "Cobré $200,000 de Nexios, es el pago mensual"
- WHEN the system processes this
- THEN the transaction SHALL be created with recurring=true
- AND SHALL have type=income, business_area=nexios

### Requirement: Budget Tracking with Warnings

The system MUST track budgets per category with: period (monthly, weekly, annual), limit amount, currency, and warning percentage. When spending reaches the warning threshold, the system SHALL notify the user. When spending exceeds the limit, the system SHALL escalate the notification. Projections SHALL be clearly labeled as estimates.

#### Scenario: Budget warning at threshold

- GIVEN a monthly budget "Comida: $100,000" with warning at 80%
- AND current month spending in comida is $82,000
- WHEN a new expense of $5,000 in comida is recorded
- THEN the system SHALL warn: "Comida: $87,000/$100,000 (87%) — estás por encima del umbral de alerta."
- AND SHALL NOT block the transaction

#### Scenario: Budget exceeded notification

- GIVEN a monthly budget "Salidas: $50,000"
- AND current month spending is $52,000
- WHEN the evening review runs
- THEN the system SHALL report: "Presupuesto Salidas excedido: $52,000/$50,000"
- AND SHALL ask if the user wants to adjust the budget or reduce spending

#### Scenario: Projection clearly labeled as estimate

- GIVEN the user asks "¿Cuánto voy a gastar este mes en total?"
- WHEN the system calculates a projection
- THEN the response SHALL include: "Proyección estimada: ~$X (basado en el gasto actual y el promedio diario)"
- AND SHALL NOT present the projection as a definite number

### Requirement: Finance Rules Enforcement

The system MUST enforce the following rules. Violations SHALL be refused with explanation:

| Rule | Behavior |
|------|----------|
| Never move money | Refuse any transfer between real accounts |
| Never connect to banks (MVP) | No API integrations with financial institutions |
| Don't assume business income = personal profit | Warn when conflating |
| Don't mix transfers with income/expense | Use transfer type for account movements |
| Keep original currency | Store in received currency; convert only with rate/source/date |
| Never give financial advice as certainty | All analysis must carry disclaimer |
| Allow corrections with audit trail | Reversal entries, not overwrites |

#### Scenario: Transfer between accounts rejected

- GIVEN the user says "Pasame $10,000 de la cuenta del banco a la de MercadoPago"
- WHEN the system processes this
- THEN it SHALL refuse with: "No muevo plata entre cuentas reales. Esto lo tenés que hacer vos desde la app del banco. Si querés, lo registro como transferencia después."

#### Scenario: Currency conversion requires metadata

- GIVEN the user reports a USD expense
- WHEN the system needs to show it in ARS for reports
- THEN the SHALL request: "¿A qué tipo de cambio querés convertir? Necesito tasa, fuente y fecha."
- AND SHALL store the original USD amount alongside the converted ARS amount with conversion metadata

#### Scenario: Correction with audit trail

- GIVEN a transaction was recorded as $10,000 but should be $15,000
- WHEN the user requests a correction
- THEN the system SHALL NOT overwrite the original
- AND SHALL create a reversal entry negating the original
- AND SHALL create a new correct entry
- AND SHALL link all three with a correction_id for audit trail
