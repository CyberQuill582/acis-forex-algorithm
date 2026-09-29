"""The cTrader Open API message model (ACIS-13 §3.1), transcribed from Spotware's `.proto` files at
the pinned commit below (ACIS-13 F-28). Only the messages ACIS uses are named.

Invariants:
  * Numbers are the proto's: a payload type or enum value here that differs from the pinned
    `.proto` is a transcription bug, never a local choice.
  * Proto2 JSON leaves out a field at its default, so a missing enum or flag reads as the proto's
    DEFAULT (`field`), never as "unknown": `isLive` absent is false, `accountType` absent is HEDGED.
  * An enum may arrive as its integer or its name (JSON enum encoding is unconfirmed, ACIS-13
    OQ-12); either decodes to the same member, and anything else is a DataQualityError.
  * Control flow keys only on these enumerated values, never on a venue's free text (C-VEN-15).
"""

from __future__ import annotations

from enum import IntEnum
from typing import Mapping, TypeVar

from core.data.errors import DataQualityError

PROTO_COMMIT = "3fd8bddfbe0cfc2ecfda079623dc4e498af11e66"   # 2025-11-13 "Fix typo in modelmessages"
HOSTS = {"demo": "demo.ctraderapi.com", "live": "live.ctraderapi.com"}   # F-01
JSON_PORT = 5036                                                         # F-01: JSON only on 5036
PRICE_SCALE = 100_000        # spot prices and relative stops are in 1/100000 of a price unit (F-13, F-23)
VOLUME_SCALE = 100           # volumes are in 0.01 of a unit (F-13)


class PT(IntEnum):
    """Payload types (OpenApiCommonModelMessages / OpenApiModelMessages `ProtoOAPayloadType`)."""
    ERROR_RES = 50
    HEARTBEAT_EVENT = 51
    APPLICATION_AUTH_REQ = 2100
    APPLICATION_AUTH_RES = 2101
    ACCOUNT_AUTH_REQ = 2102
    ACCOUNT_AUTH_RES = 2103
    NEW_ORDER_REQ = 2106
    CANCEL_ORDER_REQ = 2108
    AMEND_POSITION_SLTP_REQ = 2110
    CLOSE_POSITION_REQ = 2111
    ASSET_LIST_REQ = 2112
    ASSET_LIST_RES = 2113
    SYMBOLS_LIST_REQ = 2114
    SYMBOLS_LIST_RES = 2115
    SYMBOL_BY_ID_REQ = 2116
    SYMBOL_BY_ID_RES = 2117
    TRADER_REQ = 2121
    TRADER_RES = 2122
    TRADER_UPDATE_EVENT = 2123
    RECONCILE_REQ = 2124
    RECONCILE_RES = 2125
    EXECUTION_EVENT = 2126
    SUBSCRIBE_SPOTS_REQ = 2127
    SUBSCRIBE_SPOTS_RES = 2128
    UNSUBSCRIBE_SPOTS_REQ = 2129
    UNSUBSCRIBE_SPOTS_RES = 2130
    SPOT_EVENT = 2131
    ORDER_ERROR_EVENT = 2132
    DEAL_LIST_REQ = 2133
    DEAL_LIST_RES = 2134
    MARGIN_CHANGED_EVENT = 2141
    OA_ERROR_RES = 2142
    ACCOUNTS_TOKEN_INVALIDATED_EVENT = 2147
    CLIENT_DISCONNECT_EVENT = 2148
    GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ = 2149
    GET_ACCOUNTS_BY_ACCESS_TOKEN_RES = 2150
    ACCOUNT_DISCONNECT_EVENT = 2164
    REFRESH_TOKEN_REQ = 2173
    REFRESH_TOKEN_RES = 2174
    ORDER_LIST_REQ = 2175
    ORDER_LIST_RES = 2176
    ORDER_DETAILS_REQ = 2181
    ORDER_DETAILS_RES = 2182
    GET_POSITION_UNREALIZED_PNL_REQ = 2187
    GET_POSITION_UNREALIZED_PNL_RES = 2188


class ExecutionType(IntEnum):
    ORDER_ACCEPTED = 2
    ORDER_FILLED = 3
    ORDER_REPLACED = 4
    ORDER_CANCELLED = 5
    ORDER_EXPIRED = 6
    ORDER_REJECTED = 7
    ORDER_CANCEL_REJECTED = 8
    SWAP = 9
    DEPOSIT_WITHDRAW = 10
    ORDER_PARTIAL_FILL = 11
    BONUS_DEPOSIT_WITHDRAW = 12


class TradeSide(IntEnum):
    BUY = 1
    SELL = 2


class OrderType(IntEnum):
    MARKET = 1
    LIMIT = 2
    STOP = 3
    STOP_LOSS_TAKE_PROFIT = 4
    MARKET_RANGE = 5
    STOP_LIMIT = 6


class TimeInForce(IntEnum):
    GOOD_TILL_DATE = 1
    GOOD_TILL_CANCEL = 2
    IMMEDIATE_OR_CANCEL = 3
    FILL_OR_KILL = 4
    MARKET_ON_OPEN = 5


class AccessRights(IntEnum):
    FULL_ACCESS = 0
    CLOSE_ONLY = 1
    NO_TRADING = 2
    NO_LOGIN = 3


class AccountType(IntEnum):
    HEDGED = 0
    NETTED = 1
    SPREAD_BETTING = 2


class TradingMode(IntEnum):
    ENABLED = 0
    DISABLED_WITHOUT_PENDINGS_EXECUTION = 1
    DISABLED_WITH_PENDINGS_EXECUTION = 2
    CLOSE_ONLY_MODE = 3


class DistanceType(IntEnum):
    SYMBOL_DISTANCE_IN_POINTS = 1
    SYMBOL_DISTANCE_IN_PERCENTAGE = 2


class OrderStatus(IntEnum):
    ORDER_STATUS_ACCEPTED = 1
    ORDER_STATUS_FILLED = 2
    ORDER_STATUS_REJECTED = 3
    ORDER_STATUS_EXPIRED = 4
    ORDER_STATUS_CANCELLED = 5


class PositionStatus(IntEnum):
    POSITION_STATUS_OPEN = 1
    POSITION_STATUS_CLOSED = 2
    POSITION_STATUS_CREATED = 3
    POSITION_STATUS_ERROR = 4


class PermissionScope(IntEnum):
    SCOPE_VIEW = 0
    SCOPE_TRADE = 1


# the proto defaults the adapter reads (field name -> default), for fields JSON may omit
DEFAULTS: Mapping[str, object] = {
    "isLive": False, "accessRights": AccessRights.FULL_ACCESS, "accountType": AccountType.HEDGED,
    "tradingMode": TradingMode.ENABLED, "distanceSetIn": DistanceType.SYMBOL_DISTANCE_IN_POINTS,
    "timeInForce": TimeInForce.IMMEDIATE_OR_CANCEL, "isServerEvent": False, "enabled": False,
    "isLimitedRisk": False, "hasMore": False,
    "permissionScope": PermissionScope.SCOPE_VIEW,     # absent reads as view-only: refused (A3)
}

# inbound frames the session routes without interpreting (ACIS-13 §3.2)
FEED_EVENTS = frozenset({PT.SPOT_EVENT})
EXECUTION_EVENTS = frozenset({PT.EXECUTION_EVENT, PT.ORDER_ERROR_EVENT, PT.TRADER_UPDATE_EVENT,
                              PT.MARGIN_CHANGED_EVENT})
AUTH_EVENTS = frozenset({PT.ACCOUNT_DISCONNECT_EVENT, PT.ACCOUNTS_TOKEN_INVALIDATED_EVENT,
                         PT.CLIENT_DISCONNECT_EVENT})
ERRORS = frozenset({PT.ERROR_RES, PT.OA_ERROR_RES})

E = TypeVar("E", bound=IntEnum)


def enum_value(enum: type[E], raw: object) -> E:
    """An enum field as its integer or its name (OQ-12); anything else is refused."""
    try:
        return enum[raw] if isinstance(raw, str) else enum(raw)
    except (KeyError, ValueError) as exc:
        raise DataQualityError(enum.__name__, raw, "not a value of the pinned proto") from exc


def field(message: Mapping, name: str):
    """A field, or the proto's default when JSON omitted it; a field with no default is required."""
    if name in message:
        return message[name]
    if name in DEFAULTS:
        return DEFAULTS[name]
    raise DataQualityError(name, None, "required field missing from the venue message")
