# PARTIAL checkpoint — OANDA execution/spreads/regulatory research

Task: gather PRIMARY-SOURCE facts about OANDA's retail FX/spot-gold execution
(order execution policy, v20 API priceBound/TimeInForce/OrderFillTransaction/
PriceBucket/reject-reasons, published spreads, min/max trade size, RTS27/28,
NFA/CFTC actions). Assigned by a parent Claude Code session working on the
ACIS repo (research-only subagent, told NOT to write/modify repo files —
this checkpoint file is an exception requested directly by the session
coordinator for crash-safety, not part of the original task).

STATUS: Task is essentially COMPLETE. Full findings were already delivered
via SubagentHandback to the parent session, and a follow-up supplemental
message (new items only: XAU/USD spread, Core Pricing commission/million,
minimumTradeSize/maximumOrderUnits schema, full TransactionRejectReason +
OrderCancelReason enum lists, RTS27/28 status, fill-stats absence) was sent
via SendMessage to a peer agent (id a8bf84c528774d3ce) who was doing the
same research independently. This file is a backup of that content in case
either delivery is lost.

This file writes NOTHING to engine code/config/specs/ledger — informational
only, per coordinator instruction.

---

## 1. Order execution policy — exact quotes, URLs, grades

### [BROKER-PRIMARY] OANDA Europe Limited "ORDER EXECUTION POLICY", May 2026
URL: https://legal.oanda.com/?code=execution_policy_oel&language=en (PDF)
(linked from https://www.oanda.com/uk-en/legal/ under doc code `execution_policy_oel`)

- Principal, not agent: "We will act as principal and not as your agent when
  executing your Orders, we therefore act as the sole trading venue for those
  Orders. This means you will be dealing directly with us and not with the
  wider market." (§2.1)
- "We cannot guarantee, when executing an Order, that our price will always
  be better than a price which might have been available elsewhere." (§2.2)
- "We are not obliged to accept your Order(s) and may therefore reject any
  Order(s) in accordance with our Terms of Business." (§3.1(c))
- Pricing: "The prices shown to you are based on an average of the pricing,
  excluding outliers, available from those third parties. This average is
  our objective view of the bid and ask prices available to arms' length
  market participants in respect of transactions of a Normal Market Size..."
  (§5.1)
- Matched principal / market maker: "While we act as matched principal in
  respect of your Orders, OANDA group companies will look to the execution
  venues available to them for the pricing, hedging, and execution of your
  Orders and Trades. OANDA group companies may seek to manage their risk as
  market maker and may choose to hedge... Accordingly, this may impact the
  execution price of your Orders." (§5.5)
- Slippage — no re-quotes, symmetric: "All Orders are executed at the
  prevailing price(s) at the time the Order is processed after receipt on
  our execution server." (§11.1); "The pricing and execution components of
  our Trading Platform do not apply asymmetrical slippage parameters.
  Positive and negative slippage are handled with strict symmetry to protect
  clients from foreseeable harm during execution gaps." (§11.2)
- Order-size limits: "If the requested Transaction exceeds limits that we
  have established for the relevant Product, you may not be able to place
  your Order." (§10.2)
- Annex 1 order-type -> execution-type mapping (exact):
  - "Market FOK — A market order executed on an order execution venue at the
    most recent price appropriate for the quantity of the order. There are
    no partial fills of the order. The order is rejected/cancelled in the
    case where the order size exceeds available liquidity." (FX & Metals,
    Indices & Commodities market orders)
  - "Market IOC — ...Partial fills are possible only in the case where the
    order size exceeds available liquidity. Any remaining quantity not
    filled will be cancelled." (Equity-share market orders)
  - Stop Entry/Stop Loss/Close Out -> "Market GTC Full" (FX/Metals,
    Indices/Commodities, internally an FOK leg) or "Market GTC Partial"
    (equities, an IOC leg); unfilled remainder returns to pending state.
  - Limit/Take Profit -> "Limit GTC Full"/"Limit GTC Partial" similarly.
  - "'FOK' means 'fill or kill'"; "'IOC' means 'immediate or cancel'";
    "'GTC' means 'good 'til cancelled'"
- Price improvement as a factor (not guaranteed): "...we will consider the
  need for timely execution, availability of price improvement, liquidity
  of the Instrument in relation to the size of your Order..." (§4.2)
- No aggregation: "We will not aggregate your Trade(s) or Order(s) with
  those of any other client during execution." (§14.1)
- Volatility/gap disclosure (§12.1): execution at substantially different
  price from quoted bid/ask; delays sending orders to external market
  makers; opening prices differing from prior close; locked/crossed/
  halted/limit-up/limit-down/protected market conditions preventing
  execution.

### [BROKER-PRIMARY] OANDA Corporation (US, NFA/CFTC) — no separate written
"order execution policy" doc; instead a mandated trade-execution-report
disclosure (NFA doesn't require RTS27/28-style docs).
URL: https://www.oanda.com/us-en/legal/
- "OANDA Corporation forex customers can receive reports on trade execution.
  On request, OANDA will generate a Trade Execution Report of all the
  transactions OANDA executed, in the same currency pair, in the 15 minute
  windows before and after execution of the customer's transaction. The
  report will contain up to 15 transactions from each time period." (link
  target https://hub.oanda.com/documents/execution-report — gated/login,
  could not fetch content)
- "OANDA Corporation does not act in the capacity of your financial advisor
  or fiduciary and simply executes customer instructions."
- NFA membership: "OANDA Corporation is a registered Futures Commission
  Merchant and Retail Foreign Exchange Dealer with the Commodity Futures
  Trading Commission and is a member of the National Futures Association.
  No: 0325821."

### [BROKER-PRIMARY] "OANDA Additional Disclaimer" (US), version December 2025
URL: https://www.oanda.com/assets/documents/2003/OANDA_Additional_Disclaimer-2025.pdf
(linked from https://www.oanda.com/us-en/legal/)
- "THE FOREIGN CURRENCY TRADING YOU ARE ENTERING INTO IS NOT CONDUCTED ON AN
  EXCHANGE. OANDA IS ACTING AS A COUNTERPARTY IN THESE TRANSACTIONS AND,
  THEREFORE, ACTS AS THE BUYER WHEN YOU SELL AND THE SELLER WHEN YOU BUY. AS
  A RESULT, OANDA'S INTERESTS MAY BE IN CONFLICT WITH YOURS. UNLESS
  OTHERWISE SPECIFIED IN YOUR WRITTEN AGREEMENT OR OTHER WRITTEN DOCUMENTS,
  OANDA ESTABLISHES THE PRICES AT WHICH IT OFFERS TO TRADE WITH YOU. THE
  PRICES OANDA OFFERS MIGHT NOT BE THE BEST PRICES AVAILABLE."
- "IF OANDA ELECTS NOT TO COVER ITS OWN TRADING EXPOSURE, THEN YOU SHOULD BE
  AWARE THAT OANDA MAY MAKE MORE MONEY IF THE MARKET GOES AGAINST YOU."
- Revenue model: "For most accounts, OANDA charges no commissions, fees, or
  service charges from trading, and hence generates revenues from the
  spreads alone... you pay the equivalent of half the spread, on average,
  for each (opening or closing) trade you execute... This goes to pay for
  the costs of sales, including: (1) the cost of hedging OANDA's excess
  exposure... the spreads OANDA has to pay can be higher or lower than the
  spreads OANDA offers its clients; (2) the cost of OANDA's exposure to
  market movements before third-party hedging occurs; and (3) interest and
  swap charges that OANDA incurs."

Dead ends (404, don't re-try): oanda.com/us-en/legal/order-execution-policy/,
/eu-en/legal/order-execution-policy/, /eu-en/legal/best-execution/,
/en-gb/legal/*. Live doc system is `legal.oanda.com/?code=<code>&language=en`;
codes differ per entity (`_oel` = OANDA Europe Limited/UK; `_oc` roughly =
OANDA Corporation/US docs, though US content mostly lives directly on
oanda.com/us-en/legal/ rather than behind a doc code).

---

## 2. v20 API — exact schema text (all curled directly from raw HTML,
developer.oanda.com — NOT WebFetch-summarized, so nothing here is a
paraphrase)

Sources:
- https://developer.oanda.com/rest-live-v20/order-df/
- https://developer.oanda.com/rest-live-v20/transaction-df/
- https://developer.oanda.com/rest-live-v20/pricing-common-df/
- https://developer.oanda.com/rest-live-v20/primitives-df/

MarketOrder / priceBound / timeInForce:
- `timeInForce : (TimeInForce, required, default=FOK)` — "The time-in-force
  requested for the Market Order. Restricted to FOK or IOC for a
  MarketOrder."
- `priceBound : (PriceValue)` — "The worst price that the client is willing
  to have the Market Order filled at."
- Stop-order interaction: "If the market gaps and crosses through both the
  price and the priceBound, the Stop Order will be cancelled instead of
  being filled."

OrderFillTransaction fields:
- `fullVWAP : (PriceValue)` — "The price that all of the units of the
  OrderFill should have been filled at, in the absence of guaranteed price
  execution. This factors in the Account's current ClientPrice, used
  liquidity and the units of the OrderFill only. If no Trades were closed
  with their price clamped for guaranteed stop loss enforcement, then this
  value will match the price fields of each Trade opened, closed, and
  reduced, and they will all be the exact same."
- `fullPrice : (ClientPrice)` — "The price in effect for the account at the
  time of the Order fill."
- (deprecated) `price` — "This field is now deprecated and should no longer
  be used. The individual tradesClosed, tradeReduced and tradeOpened fields
  contain the exact/official price each unit was filled at."

PriceBucket (exact schema, from pricing-common-df):
```
PriceBucket is an application/json object with the following Schema:
{
    # The Price offered by the PriceBucket
    price : (PriceValue),
    # The amount of liquidity offered by the PriceBucket
    liquidity : (integer or decimal if available)
}
```
Tagline: "A PriceBucket represents a price available for an amount of
liquidity."

Instrument schema fields (primitives-df, exact text; NO numeric
default/example given anywhere in the static docs):
- `minimumTradeSize : (DecimalNumber)` — "The smallest number of units
  allowed to be traded for this instrument."
- `maximumTrailingStopDistance : (DecimalNumber)` — "The maximum trailing
  stop distance allowed for a trailing stop loss created for this
  instrument. Specified in price units."
- `minimumGuaranteedStopLossDistance : (DecimalNumber)`
- `minimumTrailingStopDistance : (DecimalNumber)`
- `maximumPositionSize : (DecimalNumber)` — "The maximum position size
  allowed for this instrument. Specified in units."
- `maximumOrderUnits : (DecimalNumber)` — "The maximum units allowed for an
  Order placed for this instrument. Specified in units."
- `marginRate : (DecimalNumber)` — "The margin rate for this instrument."
- These are all served dynamically per-instrument via an authenticated
  `/v20/accounts/{id}/instruments` call — I had NO API key/account access in
  this sandbox, so could NOT retrieve actual numeric values for FX or XAU.
  This is the single biggest unresolved item — needs a real or practice v20
  account to close out.

### IMPORTANT ENUM-MAPPING CORRECTION (verified against raw HTML tables,
not assumed): `MARKET_HALTED`, `FIFO_VIOLATION`, `INSUFFICIENT_LIQUIDITY`,
and the "price bound breach" reason all belong to **`OrderCancelReason`**,
NOT `TransactionRejectReason`. There is no `PRICE_BOUND_EXCEEDED` value
anywhere in the v20 spec at all. The two real analogues:
- `TransactionRejectReason.PRICE_BOUND_INVALID` — "The price bound specified
  is invalid" (pre-trade validation reject)
- `OrderCancelReason.BOUNDS_VIOLATION` — "Filling the Order would have
  violated the Order's price bound." (the actual fill-time bound breach)

Verbatim typos in OANDA's own docs (reproduce as-is if quoting for an audit
trail, do not silently fix):
- `OrderCancelReason.FIFO_VIOLATION` — "Filling the Order would have
  resulted in a a FIFO violation." (double "a")
- `OrderCancelReason.INSUFFICIENT_LIQUIDITY` — "Filling the Order wasn't
  possible because enough liquidity available." (missing "not")

### Full OrderCancelReason enum (65 names extracted from raw table,
developer.oanda.com/rest-live-v20/transaction-df/, section starting
`<a name="OrderCancelReason">`):
INTERNAL_SERVER_ERROR, ACCOUNT_LOCKED, ACCOUNT_NEW_POSITIONS_LOCKED,
ACCOUNT_ORDER_CREATION_LOCKED, ACCOUNT_ORDER_FILL_LOCKED, CLIENT_REQUEST,
MIGRATION, MARKET_HALTED, LINKED_TRADE_CLOSED, TIME_IN_FORCE_EXPIRED,
INSUFFICIENT_MARGIN, FIFO_VIOLATION, BOUNDS_VIOLATION,
CLIENT_REQUEST_REPLACED, DIVIDEND_ADJUSTMENT_REPLACED,
INSUFFICIENT_LIQUIDITY, TAKE_PROFIT_ON_FILL_GTD_TIMESTAMP_IN_PAST,
TAKE_PROFIT_ON_FILL_LOSS, LOSING_TAKE_PROFIT,
STOP_LOSS_ON_FILL_GTD_TIMESTAMP_IN_PAST, STOP_LOSS_ON_FILL_LOSS,
STOP_LOSS_ON_FILL_PRICE_DISTANCE_MAXIMUM_EXCEEDED, STOP_LOSS_ON_FILL_REQUIRED,
STOP_LOSS_ON_FILL_GUARANTEED_REQUIRED,
STOP_LOSS_ON_FILL_GUARANTEED_NOT_ALLOWED,
STOP_LOSS_ON_FILL_GUARANTEED_MINIMUM_DISTANCE_NOT_MET,
STOP_LOSS_ON_FILL_GUARANTEED_LEVEL_RESTRICTION_EXCEEDED,
STOP_LOSS_ON_FILL_GUARANTEED_HEDGING_NOT_ALLOWED,
STOP_LOSS_ON_FILL_TIME_IN_FORCE_INVALID,
STOP_LOSS_ON_FILL_TRIGGER_CONDITION_INVALID,
GUARANTEED_STOP_LOSS_ON_FILL_GTD_TIMESTAMP_IN_PAST,
GUARANTEED_STOP_LOSS_ON_FILL_LOSS,
GUARANTEED_STOP_LOSS_ON_FILL_PRICE_DISTANCE_MAXIMUM_EXCEEDED,
GUARANTEED_STOP_LOSS_ON_FILL_REQUIRED, GUARANTEED_STOP_LOSS_ON_FILL_NOT_ALLOWED,
GUARANTEED_STOP_LOSS_ON_FILL_MINIMUM_DISTANCE_NOT_MET,
GUARANTEED_STOP_LOSS_ON_FILL_LEVEL_RESTRICTION_VOLUME_EXCEEDED,
GUARANTEED_STOP_LOSS_ON_FILL_LEVEL_RESTRICTION_PRICE_RANGE_EXCEEDED,
GUARANTEED_STOP_LOSS_ON_FILL_HEDGING_NOT_ALLOWED,
GUARANTEED_STOP_LOSS_ON_FILL_TIME_IN_FORCE_INVALID,
GUARANTEED_STOP_LOSS_ON_FILL_TRIGGER_CONDITION_INVALID,
TAKE_PROFIT_ON_FILL_PRICE_DISTANCE_MAXIMUM_EXCEEDED,
TRAILING_STOP_LOSS_ON_FILL_GTD_TIMESTAMP_IN_PAST,
CLIENT_TRADE_ID_ALREADY_EXISTS, POSITION_CLOSEOUT_FAILED,
OPEN_TRADES_ALLOWED_EXCEEDED, PENDING_ORDERS_ALLOWED_EXCEEDED,
TAKE_PROFIT_ON_FILL_CLIENT_ORDER_ID_ALREADY_EXISTS,
STOP_LOSS_ON_FILL_CLIENT_ORDER_ID_ALREADY_EXISTS,
GUARANTEED_STOP_LOSS_ON_FILL_CLIENT_ORDER_ID_ALREADY_EXISTS,
TRAILING_STOP_LOSS_ON_FILL_CLIENT_ORDER_ID_ALREADY_EXISTS,
POSITION_SIZE_EXCEEDED, HEDGING_GSLO_VIOLATION,
ACCOUNT_POSITION_VALUE_LIMIT_EXCEEDED, INSTRUMENT_BID_REDUCE_ONLY,
INSTRUMENT_ASK_REDUCE_ONLY, INSTRUMENT_BID_HALTED, INSTRUMENT_ASK_HALTED,
STOP_LOSS_ON_FILL_GUARANTEED_BID_HALTED,
STOP_LOSS_ON_FILL_GUARANTEED_ASK_HALTED,
GUARANTEED_STOP_LOSS_ON_FILL_BID_HALTED,
GUARANTEED_STOP_LOSS_ON_FILL_ASK_HALTED, FIFO_VIOLATION_SAFEGUARD_VIOLATION,
FIFO_VIOLATION_SAFEGUARD_PARTIAL_CLOSE_VIOLATION,
ORDERS_ON_FILL_RMO_MUTUAL_EXCLUSIVITY_MUTUALLY_EXCLUSIVE_VIOLATION
(+ likely one more, "...GSLO_EXCLUDES_OTHERS_VIOLATION", at my extraction
boundary — not fully captured, re-fetch transaction-df and look right after
this line if the exact tail matters)

### Full TransactionRejectReason enum (198 names — pre-trade validation
enum, separate table, section starting `<a name="TransactionRejectReason">`):
INTERNAL_SERVER_ERROR, INSTRUMENT_PRICE_UNKNOWN, ACCOUNT_NOT_ACTIVE,
ACCOUNT_LOCKED, ACCOUNT_ORDER_CREATION_LOCKED, ACCOUNT_CONFIGURATION_LOCKED,
ACCOUNT_DEPOSIT_LOCKED, ACCOUNT_WITHDRAWAL_LOCKED,
ACCOUNT_ORDER_CANCEL_LOCKED, INSTRUMENT_NOT_TRADEABLE,
PENDING_ORDERS_ALLOWED_EXCEEDED, ORDER_ID_UNSPECIFIED, ORDER_DOESNT_EXIST,
ORDER_IDENTIFIER_INCONSISTENCY, TRADE_ID_UNSPECIFIED, TRADE_DOESNT_EXIST,
TRADE_IDENTIFIER_INCONSISTENCY, INSUFFICIENT_MARGIN, INSTRUMENT_MISSING,
INSTRUMENT_UNKNOWN, UNITS_MISSING, UNITS_INVALID, UNITS_PRECISION_EXCEEDED,
UNITS_LIMIT_EXCEEDED, UNITS_MINIMUM_NOT_MET, PRICE_MISSING, PRICE_INVALID,
PRICE_PRECISION_EXCEEDED, PRICE_DISTANCE_MISSING, PRICE_DISTANCE_INVALID,
PRICE_DISTANCE_PRECISION_EXCEEDED, PRICE_DISTANCE_MAXIMUM_EXCEEDED,
PRICE_DISTANCE_MINIMUM_NOT_MET, TIME_IN_FORCE_MISSING, TIME_IN_FORCE_INVALID,
TIME_IN_FORCE_GTD_TIMESTAMP_MISSING, TIME_IN_FORCE_GTD_TIMESTAMP_IN_PAST,
PRICE_BOUND_INVALID, PRICE_BOUND_PRECISION_EXCEEDED,
ORDERS_ON_FILL_DUPLICATE_CLIENT_ORDER_IDS,
TRADE_ON_FILL_CLIENT_EXTENSIONS_NOT_SUPPORTED, CLIENT_ORDER_ID_INVALID,
CLIENT_ORDER_ID_ALREADY_EXISTS, CLIENT_ORDER_TAG_INVALID,
CLIENT_ORDER_COMMENT_INVALID, CLIENT_TRADE_ID_INVALID,
CLIENT_TRADE_ID_ALREADY_EXISTS, CLIENT_TRADE_TAG_INVALID,
CLIENT_TRADE_COMMENT_INVALID, ORDER_FILL_POSITION_ACTION_MISSING,
ORDER_FILL_POSITION_ACTION_INVALID, TRIGGER_CONDITION_MISSING,
TRIGGER_CONDITION_INVALID, ORDER_PARTIAL_FILL_OPTION_MISSING,
ORDER_PARTIAL_FILL_OPTION_INVALID, INVALID_REISSUE_IMMEDIATE_PARTIAL_FILL,
ORDERS_ON_FILL_RMO_MUTUAL_EXCLUSIVITY_MUTUALLY_EXCLUSIVE_VIOLATION,
ORDERS_ON_FILL_RMO_MUTUAL_EXCLUSIVITY_GSLO_EXCLUDES_OTHERS_VIOLATION,
TAKE_PROFIT_ORDER_ALREADY_EXISTS,
TAKE_PROFIT_ORDER_WOULD_VIOLATE_FIFO_VIOLATION_SAFEGUARD,
TAKE_PROFIT_ON_FILL_PRICE_MISSING, TAKE_PROFIT_ON_FILL_PRICE_INVALID,
TAKE_PROFIT_ON_FILL_PRICE_PRECISION_EXCEEDED,
TAKE_PROFIT_ON_FILL_TIME_IN_FORCE_MISSING,
TAKE_PROFIT_ON_FILL_TIME_IN_FORCE_INVALID,
TAKE_PROFIT_ON_FILL_GTD_TIMESTAMP_MISSING,
TAKE_PROFIT_ON_FILL_GTD_TIMESTAMP_IN_PAST,
TAKE_PROFIT_ON_FILL_CLIENT_ORDER_ID_INVALID,
TAKE_PROFIT_ON_FILL_CLIENT_ORDER_TAG_INVALID,
TAKE_PROFIT_ON_FILL_CLIENT_ORDER_COMMENT_INVALID,
TAKE_PROFIT_ON_FILL_TRIGGER_CONDITION_MISSING,
TAKE_PROFIT_ON_FILL_TRIGGER_CONDITION_INVALID, STOP_LOSS_ORDER_ALREADY_EXISTS,
STOP_LOSS_ORDER_GUARANTEED_REQUIRED,
STOP_LOSS_ORDER_GUARANTEED_PRICE_WITHIN_SPREAD,
STOP_LOSS_ORDER_GUARANTEED_NOT_ALLOWED,
STOP_LOSS_ORDER_GUARANTEED_HALTED_CREATE_VIOLATION,
STOP_LOSS_ORDER_GUARANTEED_HALTED_TIGHTEN_VIOLATION,
STOP_LOSS_ORDER_GUARANTEED_HEDGING_NOT_ALLOWED,
STOP_LOSS_ORDER_GUARANTEED_MINIMUM_DISTANCE_NOT_MET,
STOP_LOSS_ORDER_NOT_CANCELABLE, STOP_LOSS_ORDER_NOT_REPLACEABLE,
STOP_LOSS_ORDER_GUARANTEED_LEVEL_RESTRICTION_EXCEEDED,
STOP_LOSS_ORDER_PRICE_AND_DISTANCE_BOTH_SPECIFIED,
STOP_LOSS_ORDER_PRICE_AND_DISTANCE_BOTH_MISSING,
STOP_LOSS_ORDER_WOULD_VIOLATE_FIFO_VIOLATION_SAFEGUARD,
STOP_LOSS_ORDER_RMO_MUTUAL_EXCLUSIVITY_MUTUALLY_EXCLUSIVE_VIOLATION,
STOP_LOSS_ORDER_RMO_MUTUAL_EXCLUSIVITY_GSLO_EXCLUDES_OTHERS_VIOLATION,
STOP_LOSS_ON_FILL_REQUIRED_FOR_PENDING_ORDER,
STOP_LOSS_ON_FILL_GUARANTEED_NOT_ALLOWED, STOP_LOSS_ON_FILL_GUARANTEED_REQUIRED,
STOP_LOSS_ON_FILL_PRICE_MISSING, STOP_LOSS_ON_FILL_PRICE_INVALID,
STOP_LOSS_ON_FILL_PRICE_PRECISION_EXCEEDED,
STOP_LOSS_ON_FILL_GUARANTEED_MINIMUM_DISTANCE_NOT_MET,
STOP_LOSS_ON_FILL_GUARANTEED_LEVEL_RESTRICTION_EXCEEDED,
STOP_LOSS_ON_FILL_DISTANCE_INVALID,
STOP_LOSS_ON_FILL_PRICE_DISTANCE_MAXIMUM_EXCEEDED,
STOP_LOSS_ON_FILL_DISTANCE_PRECISION_EXCEEDED,
STOP_LOSS_ON_FILL_PRICE_AND_DISTANCE_BOTH_SPECIFIED,
STOP_LOSS_ON_FILL_PRICE_AND_DISTANCE_BOTH_MISSING,
STOP_LOSS_ON_FILL_TIME_IN_FORCE_MISSING, STOP_LOSS_ON_FILL_TIME_IN_FORCE_INVALID,
STOP_LOSS_ON_FILL_GTD_TIMESTAMP_MISSING, STOP_LOSS_ON_FILL_GTD_TIMESTAMP_IN_PAST,
STOP_LOSS_ON_FILL_CLIENT_ORDER_ID_INVALID,
STOP_LOSS_ON_FILL_CLIENT_ORDER_TAG_INVALID,
STOP_LOSS_ON_FILL_CLIENT_ORDER_COMMENT_INVALID,
STOP_LOSS_ON_FILL_TRIGGER_CONDITION_MISSING,
STOP_LOSS_ON_FILL_TRIGGER_CONDITION_INVALID,
GUARANTEED_STOP_LOSS_ORDER_ALREADY_EXISTS, GUARANTEED_STOP_LOSS_ORDER_REQUIRED,
GUARANTEED_STOP_LOSS_ORDER_PRICE_WITHIN_SPREAD,
GUARANTEED_STOP_LOSS_ORDER_NOT_ALLOWED,
GUARANTEED_STOP_LOSS_ORDER_HALTED_CREATE_VIOLATION,
GUARANTEED_STOP_LOSS_ORDER_CREATE_VIOLATION,
GUARANTEED_STOP_LOSS_ORDER_HALTED_TIGHTEN_VIOLATION,
GUARANTEED_STOP_LOSS_ORDER_TIGHTEN_VIOLATION,
GUARANTEED_STOP_LOSS_ORDER_HEDGING_NOT_ALLOWED,
GUARANTEED_STOP_LOSS_ORDER_MINIMUM_DISTANCE_NOT_MET,
GUARANTEED_STOP_LOSS_ORDER_NOT_CANCELABLE,
GUARANTEED_STOP_LOSS_ORDER_HALTED_NOT_CANCELABLE,
GUARANTEED_STOP_LOSS_ORDER_NOT_REPLACEABLE,
GUARANTEED_STOP_LOSS_ORDER_HALTED_NOT_REPLACEABLE,
GUARANTEED_STOP_LOSS_ORDER_LEVEL_RESTRICTION_VOLUME_EXCEEDED,
GUARANTEED_STOP_LOSS_ORDER_LEVEL_RESTRICTION_PRICE_RANGE_EXCEEDED,
GUARANTEED_STOP_LOSS_ORDER_PRICE_AND_DISTANCE_BOTH_SPECIFIED,
GUARANTEED_STOP_LOSS_ORDER_PRICE_AND_DISTANCE_BOTH_MISSING,
GUARANTEED_STOP_LOSS_ORDER_WOULD_VIOLATE_FIFO_VIOLATION_SAFEGUARD,
GUARANTEED_STOP_LOSS_ORDER_RMO_MUTUAL_EXCLUSIVITY_MUTUALLY_EXCLUSIVE_VIOLATION,
GUARANTEED_STOP_LOSS_ORDER_RMO_MUTUAL_EXCLUSIVITY_GSLO_EXCLUDES_OTHERS_VIOLATION,
GUARANTEED_STOP_LOSS_ON_FILL_REQUIRED_FOR_PENDING_ORDER,
GUARANTEED_STOP_LOSS_ON_FILL_NOT_ALLOWED, GUARANTEED_STOP_LOSS_ON_FILL_REQUIRED,
GUARANTEED_STOP_LOSS_ON_FILL_PRICE_MISSING,
GUARANTEED_STOP_LOSS_ON_FILL_PRICE_INVALID,
GUARANTEED_STOP_LOSS_ON_FILL_PRICE_PRECISION_EXCEEDED,
GUARANTEED_STOP_LOSS_ON_FILL_MINIMUM_DISTANCE_NOT_MET,
GUARANTEED_STOP_LOSS_ON_FILL_LEVEL_RESTRICTION_VOLUME_EXCEEDED,
GUARANTEED_STOP_LOSS_ON_FILL_LEVEL_RESTRICTION_PRICE_RANGE_EXCEEDED,
GUARANTEED_STOP_LOSS_ON_FILL_DISTANCE_INVALID,
GUARANTEED_STOP_LOSS_ON_FILL_PRICE_DISTANCE_MAXIMUM_EXCEEDED,
GUARANTEED_STOP_LOSS_ON_FILL_DISTANCE_PRECISION_EXCEEDED,
GUARANTEED_STOP_LOSS_ON_FILL_PRICE_AND_DISTANCE_BOTH_SPECIFIED,
GUARANTEED_STOP_LOSS_ON_FILL_PRICE_AND_DISTANCE_BOTH_MISSING,
GUARANTEED_STOP_LOSS_ON_FILL_TIME_IN_FORCE_MISSING,
GUARANTEED_STOP_LOSS_ON_FILL_TIME_IN_FORCE_INVALID,
GUARANTEED_STOP_LOSS_ON_FILL_GTD_TIMESTAMP_MISSING,
GUARANTEED_STOP_LOSS_ON_FILL_GTD_TIMESTAMP_IN_PAST,
GUARANTEED_STOP_LOSS_ON_FILL_CLIENT_ORDER_ID_INVALID,
GUARANTEED_STOP_LOSS_ON_FILL_CLIENT_ORDER_TAG_INVALID,
GUARANTEED_STOP_LOSS_ON_FILL_CLIENT_ORDER_COMMENT_INVALID,
GUARANTEED_STOP_LOSS_ON_FILL_TRIGGER_CONDITION_MISSING,
GUARANTEED_STOP_LOSS_ON_FILL_TRIGGER_CONDITION_INVALID,
TRAILING_STOP_LOSS_ORDER_ALREADY_EXISTS,
TRAILING_STOP_LOSS_ORDER_WOULD_VIOLATE_FIFO_VIOLATION_SAFEGUARD,
TRAILING_STOP_LOSS_ORDER_RMO_MUTUAL_EXCLUSIVITY_MUTUALLY_EXCLUSIVE_VIOLATION,
TRAILING_STOP_LOSS_ORDER_RMO_MUTUAL_EXCLUSIVITY_GSLO_EXCLUDES_OTHERS_VIOLATION,
TRAILING_STOP_LOSS_ON_FILL_PRICE_DISTANCE_MISSING,
TRAILING_STOP_LOSS_ON_FILL_PRICE_DISTANCE_INVALID,
TRAILING_STOP_LOSS_ON_FILL_PRICE_DISTANCE_PRECISION_EXCEEDED,
TRAILING_STOP_LOSS_ON_FILL_PRICE_DISTANCE_MAXIMUM_EXCEEDED,
TRAILING_STOP_LOSS_ON_FILL_PRICE_DISTANCE_MINIMUM_NOT_MET,
TRAILING_STOP_LOSS_ON_FILL_TIME_IN_FORCE_MISSING,
TRAILING_STOP_LOSS_ON_FILL_TIME_IN_FORCE_INVALID,
TRAILING_STOP_LOSS_ON_FILL_GTD_TIMESTAMP_MISSING,
TRAILING_STOP_LOSS_ON_FILL_GTD_TIMESTAMP_IN_PAST,
TRAILING_STOP_LOSS_ON_FILL_CLIENT_ORDER_ID_INVALID,
TRAILING_STOP_LOSS_ON_FILL_CLIENT_ORDER_TAG_INVALID,
TRAILING_STOP_LOSS_ON_FILL_CLIENT_ORDER_COMMENT_INVALID,
TRAILING_STOP_LOSS_ORDERS_NOT_SUPPORTED,
TRAILING_STOP_LOSS_ON_FILL_TRIGGER_CONDITION_MISSING,
TRAILING_STOP_LOSS_ON_FILL_TRIGGER_CONDITION_INVALID, CLOSE_TRADE_TYPE_MISSING,
CLOSE_TRADE_PARTIAL_UNITS_MISSING, CLOSE_TRADE_UNITS_EXCEED_TRADE_SIZE,
CLOSEOUT_POSITION_DOESNT_EXIST, CLOSEOUT_POSITION_INCOMPLETE_SPECIFICATION,
CLOSEOUT_POSITION_UNITS_EXCEED_POSITION_SIZE, CLOSEOUT_POSITION_REJECT,
CLOSEOUT_POSITION_PARTIAL_UNITS_MISSING, MARKUP_GROUP_ID_INVALID,
POSITION_AGGREGATION_MODE_INVALID, ADMIN_CONFIGURE_DATA_MISSING,
MARGIN_RATE_INVALID, MARGIN_RATE_WOULD_TRIGGER_CLOSEOUT, ALIAS_INVALID,
CLIENT_CONFIGURE_DATA_MISSING, MARGIN_RATE_WOULD_TRIGGER_MARGIN_CALL,
AMOUNT_INVALID, INSUFFICIENT_FUNDS, AMOUNT_MISSING, FUNDING_REASON_MISSING,
OCA_ORDER_IDS_STOP_LOSS_NOT_ALLOWED, CLIENT_EXTENSIONS_DATA_MISSING,
REPLACING_ORDER_INVALID, REPLACING_TRADE_ID_INVALID,
ORDER_CANCEL_WOULD_TRIGGER_CLOSEOUT (+ a handful more truncated at my
extraction boundary — re-fetch transaction-df for the exact tail if the last
~10-20 values matter).

---

## 3. Published spreads (LIVE, pulled directly from OANDA's own API,
2026-09-16 — [BROKER-PRIMARY])

Two different OANDA-published spread views exist, with DIFFERENT numbers —
do not conflate them:

### (A) Static "typical spread" table — oanda.com/us-en/trading/our-pricing/
FX-only, 10 pairs, no metals row. Exact numbers (pips) as rendered in the
static HTML table (`FX pair | Spread`):
AUD/USD 1.4, EUR/GBP 1.7, EUR/JPY 1.8, EUR/USD 1.4, GBP/JPY 3.1, GBP/USD 2.0,
NZD/USD 1.7, USD/CAD 2.2, USD/CHF 1.8, USD/JPY 1.4

### (B) Live spread-stability-and-average API (backs the JS-rendered
spreads-margin / historical-spreads pages)
Endpoint: https://labs-api.oanda.com/v1/spreads/spread-stability-and-average?division=OC&locale=en&instrument=<PAIR>
Methodology (exact quote): "The average spread is calculated as a
time-weighted** 'mean' (average) of our quoted spread for the last month
and last three months. We break this down into two periods, '24 hours' and
'excluding 5 pm to 7 pm Eastern,' because spreads during this time are
generally wider coming up to the close of the U.S. trading day." Footnote:
"**Time-weighted refers to the time a spread was displayed rather than
using the number of prices published with a given spread."
Stability metric description: "The quoted spread was at the value stated,
or better, 50% and 80% of the time during open trading hours."
"You can view an average, minimum, and maximum spread calculated over
15-minute intervals." (historical-spreads page)

Pulled 2026-09-16 (date field in JSON says "2026-09"):
| Pair | 50%-time | 80%-time | Avg24h(1mo) | AvgBizHrs(1mo) | Avg24h(3mo) |
|---|---|---|---|---|---|
| EUR/USD | 1.6 | 1.6 | 1.650513 | 1.557796 | 1.696036 |
| GBP/USD | 1.8 | 2.0 | 2.19839 | 1.828797 | 2.271502 |
| USD/JPY | 1.5 | 1.6 | 1.689881 | 1.516583 | 1.721334 |
| AUD/USD | 1.3 | 1.3 | 1.503387 | 1.316195 | 1.485666 |
| USD/CHF | 1.6 | 1.7 | 1.892968 | 1.589008 | 1.921109 |
| USD/CAD | 1.8 | 1.8 | 1.998851 | 1.766014 | 2.078626 |
| NZD/USD | 2.4 | 2.4 | 2.570739 | 2.35788 | 2.605602 |
| XAU/USD (Gold) | 56.1 | 63.2 | 57.101513 | 56.453498 | 61.481898 (3mo 50%/80%: 60.3/68.1) |

XAU/USD unit is NOT labeled in the JSON — inferred (not confirmed) to be the
2nd-decimal price unit given it's the same endpoint/scale convention as FX
pairs; i.e. probably ~$0.56-0.68 spread, not 56-68 whole dollars. Flag as
[BROKER-PRIMARY, unit inferred] if using this number.

No "% filled at requested price or better" or "average execution speed in
ms" disclosure found anywhere (US, UK, EU/Poland legal pages all checked).
Treat as confirmed-absent unless someone finds otherwise; closest analogues
are the 50%/80% spread-stability stat above and the on-request US Trade
Execution Report (content gated, could not verify what it actually contains).

---

## 4. Minimum/maximum trade size, partial fills

- Partial-fill behavior: confirmed via the OANDA Europe Limited Order
  Execution Policy Annex 1 (quoted fully in §1 above) — FOK legs never
  partially fill (reject/cancel instead), IOC legs partially fill when size
  exceeds available liquidity, remainder returns to pending book (for
  Stop/Limit-derived orders) or is cancelled (for plain Market IOC, i.e.
  equities).
- `TransactionRejectReason.UNITS_MINIMUM_NOT_MET` / `.UNITS_LIMIT_EXCEEDED`
  confirm the concepts of min/max exist at instrument/account level.
- Actual NUMERIC minimum/maximum per instrument (FX, XAU): NOT found in any
  static public doc (instrument-df and primitives-df give only the schema/
  field descriptions, no example values). These are almost certainly served
  only via the authenticated `/v20/accounts/{id}/instruments` endpoint. I
  had no API key/account in this sandbox — this is the main open item if
  someone needs exact numbers rather than the schema.
- The commonly-repeated "OANDA lets you trade 1 unit" claim: could NOT
  re-confirm against a primary OANDA source in this pass. Don't cite as
  fact without hitting the instruments endpoint.

Commission/pricing (found while looking, not originally asked but relevant
to §3-4 context):
- Core Pricing plan, US: "Enjoy our lowest spreads and commissions of only
  $0.70 per 10,000 units traded, when you deposit $10K or more and sign
  up." = $70/million units, one side. URL:
  https://join.oanda.com/us-en/core-spreads-new-clients/
- "Commission charges are assessed on the buy and sell sides of a trade.
  Trade sizes greater or smaller than 100,000 will be charged on a pro-rata
  basis. The minimum commission of is $0.01 per trade." [sic] — URL:
  https://www.oanda.com/us-en/trading/our-pricing/
- Elite Trader rebate tier: "Earn cash rebates from US$5 to US$17 per
  million with our Elite Trader program." (same page)

---

## 5. RTS 27/28 and NFA/CFTC regulatory actions

- RTS 27/28: NONE currently published by any OANDA entity. OANDA Europe
  Limited's live Order Execution Policy (May 2026) makes zero mention of
  RTS27/28, only "FCA Consumer Duty" — consistent with ESMA suspending the
  RTS27 quarterly report obligation EU-wide from mid-2021 and the FCA
  removing the equivalent obligation post-Brexit. Could NOT check
  Wayback Machine for pre-2021 archived reports — web.archive.org's CDX API
  returned 503 "Temporarily Offline" when tried. Retry later:
  `http://web.archive.org/cdx/search/cdx?url=oanda.com*&filter=urlkey:.*rts.*`

- [REGULATORY] CFTC action found (real, on cftc.gov — NOT a 2017 action;
  found no 2017 CFTC action in CFTC's own site search; this 2020 one is what
  exists):
  URL: https://www.cftc.gov/PressRoom/PressReleases/8224-20
  Order PDF: https://www.cftc.gov/media/4436/enfoandacorporationorder082120/download
  "CFTC Orders Toronto-Based Firm to Pay $500,000 for Violating Capital,
  Reporting, and Supervision Rules" (2020-08-21)
  "The Commodity Futures Trading Commission today issued an order filing
  and settling charges against OANDA Corporation, a futures commission
  merchant (FCM) and retail foreign exchange dealer (RFED) headquartered in
  Toronto, Canada, for violating certain capital, reporting, and supervision
  rules." / "Specifically, OANDA failed to meet minimum net capital
  requirements, violated the equity withdrawal restriction in making
  dividend payments on three occasions, failed to meet certain reporting
  requirements, and failed to diligently supervise matters related to its
  business as a CFTC registrant. The order requires OANDA to pay a $500,000
  civil monetary penalty and to cease and desist from any further
  violations of CFTC regulations, as charged." / "OANDA failed to meet net
  capital requirements from April 26, 2019 to August 21, 2019 and made
  dividend payments on October 15, 2018, April 26, 2019, and May 28, 2019 in
  violation of the equity withdrawal restriction." / Mitigating: "The order
  also notes that the Division of Enforcement found no indication that
  customers suffered losses as a result of the firm's net capital and
  equity withdrawal restriction violations."
  NOTE: this is about capital/reporting/supervision, NOT execution
  quality/pricing.

- Reparations/arbitration docket entries found (leads only, dispositions not
  fetched): Haskia Hasson v. OANDA Corporation (CFTC Docket No. 20-R017),
  Alex Lemu v. Oanda Corp., Henri Guerin v. Oanda Corp. (CFTC Docket No.
  12-R-017), Romane Soliman v. OANDA Corporation. Found via
  https://www.cftc.gov/solr-search/content?keys=OANDA

- NFA membership number (from OANDA's own site, not independently
  re-verified via NFA BASIC — my direct nfa.futures.org link attempt hit a
  redirect/expired-session page): "No: 0325821." Re-query NFA BASIC fresh by
  firm name "OANDA Corporation" at nfa.futures.org/BasicNet/ if full
  disciplinary history is needed.

---

## Grading summary
[BROKER-PRIMARY]: OANDA Europe Limited Order Execution Policy (May 2026);
OANDA US legal page + Additional Disclaimer PDF (Dec 2025); Core Pricing /
our-pricing marketing pages; developer.oanda.com v20 API docs (order-df,
transaction-df, pricing-common-df, primitives-df); labs-api.oanda.com live
spreads data (Sept 2026).
[REGULATORY]: CFTC press release 8224-20 + order PDF (2020); CFTC docket
search listing; NFA membership number as stated by OANDA (not independently
re-verified via NFA BASIC in this session).
[UNVERIFIABLE]: numeric min/max order size per instrument (needs
authenticated v20 account); "1 unit minimum" common claim; "% filled at
requested price"/"execution speed in ms" disclosure (appears not to exist);
historical RTS27/28 PDFs (Wayback Machine was down at fetch time, not
confirmed absent vs. just inaccessible); XAU/USD spread unit in the
labs-api response (value present, unit inferred not confirmed).

## Still open if anyone picks this back up
1. Get real minimumTradeSize/maximumOrderUnits/maximumPositionSize numbers
   for FX majors and XAU_USD from an authenticated v20 account's
   `/v20/accounts/{id}/instruments` call (practice account is fine).
2. Retry Wayback Machine CDX API once archive.org is back up, for any
   pre-2021 OANDA RTS27/28 PDFs.
3. Confirm the XAU/USD spread unit from labs-api (56.1 etc.) against a
   labeled source (e.g. actually open the historical-spreads chart in a
   real browser and read the axis label/tooltip).
4. If needed, log into hub.oanda.com/documents/execution-report (requires
   an OANDA login) to see what the actual US Trade Execution Report format
   contains.
5. Re-verify NFA membership/compliance history directly via
   nfa.futures.org/BasicNet/ (my link attempt failed on a redirect).

Local raw source files (HTML/PDF/JSON) were saved under /tmp in the research
sandbox during this session (e.g. /tmp/exec_policy_oel.pdf, /tmp/oanda_tx.html,
/tmp/disclaimer.pdf, /tmp/our_pricing.html, /tmp/core_spreads.html,
/tmp/*.json) — these are ephemeral to that sandbox and will NOT persist to a
future session; re-fetch the URLs above if needed.
