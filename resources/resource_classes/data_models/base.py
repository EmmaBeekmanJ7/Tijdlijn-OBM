"""Base class module"""

from __future__ import annotations

from dataclasses import fields, is_dataclass, MISSING
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    ClassVar,
)
from zoneinfo import ZoneInfo

NL_TZ = ZoneInfo("Europe/Amsterdam")
UTC_TZ = ZoneInfo("UTC")
T = TypeVar("T", bound="BaseModel")


class BaseModel:
    """
    Lightweight base with to_dict / from_dict.
    - DATE_FORMAT_MAP:    output formats per field (strptime for serialize)
    - DATE_INPUT_FORMATS: list of accepted input formats per field (for parse)
    """

    DATE_FORMAT_MAP: ClassVar[Dict[str, str]] = {}
    DATE_INPUT_FORMATS: ClassVar[Dict[str, List[str]]] = {}
    OUTPUT_TZ_NAME: ClassVar[str] = "Europe/Amsterdam"
    INPUT_NAIVE_TZ_NAME: ClassVar[str] = "Europe/Amsterdam"

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in fields(self):  # type: ignore
            name = f.name
            value = getattr(self, name)
            out[name] = self._serialize_value(name, value, f.type)
        return out

    @classmethod
    def from_dict(cls: Type[T], data: Mapping[str, Any]) -> T:
        kwargs: Dict[str, Any] = {}
        for f in fields(cls):  # type: ignore
            name = f.name
            typ = f.type
            if name in data:
                kwargs[name] = cls._deserialize_value(name, data[name], typ)
            else:
                if (
                    f.default is not MISSING
                    or getattr(f, "default_factory", MISSING) is not MISSING
                ):
                    continue
                kwargs[name] = None
        return cls(**kwargs)  # type: ignore[misc]

    # --- hooks (override if needed) ---
    def _serialize_field(self, name: str, value: Any, typ: Any) -> Any:
        return MISSING

    @classmethod
    def _deserialize_field(cls, name: str, value: Any, typ: Any) -> Any:
        return MISSING

    # --- internals ---
    def _serialize_value(self, name: str, value: Any, typ: Any) -> Any:
        hook = self._serialize_field(name, value, typ)
        if hook is not MISSING:
            return hook
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo(self.OUTPUT_TZ_NAME))
            value = value.astimezone(ZoneInfo(self.OUTPUT_TZ_NAME))

            fmt = (self.DATE_FORMAT_MAP or {}).get(name)
            return value.strftime(fmt) if fmt else value.isoformat()
        if is_dataclass(value):
            if hasattr(value, "to_dict"):
                return value.to_dict()  # type: ignore
            return {
                f.name: self._serialize_value(f.name, getattr(value, f.name), f.type)
                for f in fields(value)
            }
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(name, v, None) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(name, v, None) for k, v in value.items()}
        return value

    @classmethod
    def _deserialize_value(cls, name: str, value: Any, typ: Any) -> Any:
        hook = cls._deserialize_field(name, value, typ)
        if hook is not MISSING:
            return hook

        origin = get_origin(typ)

        # Coalesce None naar lege container als mogelijk
        if value is None:
            if hasattr(typ, "__dataclass_fields__"):
                try:
                    return typ()
                except TypeError:
                    return None
            if hasattr(typ, "from_dict") and callable(getattr(typ, "from_dict")):
                try:
                    return typ()
                except TypeError:
                    return None
            return None

        # Container/wrapper types die zelf from_dict hebben (accepteert list of dict)
        if hasattr(typ, "from_dict") and callable(getattr(typ, "from_dict")):
            return typ.from_dict(value)  # type: ignore[attr-defined]

        # Optional/Union
        if origin is Union:
            args = [a for a in get_args(typ) if a is not type(None)]
            if len(args) == 1:
                return cls._deserialize_value(name, value, args[0])

        # datetime parsing
        if typ is datetime or (
            origin is Union and any(t is datetime for t in get_args(typ))
        ):
            for fmt in (getattr(cls, "DATE_INPUT_FORMATS", {}) or {}).get(name, []):
                try:
                    dt = datetime.strptime(value, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=ZoneInfo(cls.INPUT_NAIVE_TZ_NAME))
                    return dt
                except (ValueError, TypeError):
                    pass

            fmt_out = (getattr(cls, "DATE_FORMAT_MAP", None) or {}).get(name)
            if fmt_out:
                try:
                    dt = datetime.strptime(value, fmt_out)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=ZoneInfo(cls.INPUT_NAIVE_TZ_NAME))
                    return dt
                except (ValueError, TypeError):
                    pass

            try:
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo(cls.INPUT_NAIVE_TZ_NAME))
                return dt
            except (ValueError, TypeError):
                pass

            for fallback in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(value, fallback)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=ZoneInfo(cls.INPUT_NAIVE_TZ_NAME))
                    return dt
                except (ValueError, TypeError):
                    continue

            raise ValueError(f"Invalid datetime for field '{name}': {value!r}")

        # nested dataclasses (mapping)
        if hasattr(typ, "__dataclass_fields__") and isinstance(value, Mapping):
            if hasattr(typ, "from_dict"):
                return typ.from_dict(value)
            return typ(**value)

        # lists
        if origin in (list, List, tuple):
            inner = get_args(typ)[0] if get_args(typ) else Any
            return [cls._deserialize_value(name, v, inner) for v in value]

        # dicts
        if origin and "dict" in str(origin):
            val_type = (
                get_args(typ)[1] if get_args(typ) and len(get_args(typ)) == 2 else Any
            )
            return {
                k: cls._deserialize_value(name, v, val_type) for k, v in value.items()
            }

        return value
