import re
import sys
from datetime import datetime
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError, ConfigDict

from apps.globals import (
    OUTPUT, NODATA_CODE, STRING_TRUE, STRING_FALSE, SHOW, MERGE, ORDERBY
)

class QueryParameters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Network, Station, Location, Channel
    network: Optional[str] = Field(default="*", alias="net")
    station: Optional[str] = Field(default="*", alias="sta")
    location: Optional[str] = Field(default="*", alias="loc")
    channel: Optional[str] = Field(default="*", alias="cha")

    # Time inputs (can be string or datetime)
    # Note: check_base_parameters might convert these to datetime objects BEFORE Pydantic sees them.
    starttime: Optional[str | datetime] = Field(default=None, alias="start")
    endtime: Optional[str | datetime] = Field(default=None, alias="end")

    # Options
    quality: str = Field(default="*")
    merge: str = Field(default="")
    mergegaps: Optional[float] = Field(default=None)
    orderby: Optional[str] = Field(default=None)
    limit: Optional[int] = Field(default=None)
    includerestricted: bool = Field(default=False)
    format: str = Field(default="text")
    nodata: str = Field(default="204")
    show: str = Field(default="")
    
    # Internal usage fields NOT in parameters but used in logic
    # We can use exclude=True in export or just keep them as Optional
    
    @field_validator('network')
    @classmethod
    def validate_network(cls, v: Optional[str]) -> str:
        if not v:
            return "*"
        for part in v.split(','):
            if not re.match(r"[A-Za-z0-9*?]{1,2}$", part):
                 raise ValueError(f"Invalid network code: {part}")
        return v

    @field_validator('station')
    @classmethod
    def validate_station(cls, v: Optional[str]) -> str:
        if not v:
            return "*"
        for part in v.split(','):
            if not re.match(r"[A-Za-z0-9*?]{1,5}$", part):
                 raise ValueError(f"Invalid station code: {part}")
        return v

    @field_validator('location')
    @classmethod
    def validate_location(cls, v: Optional[str]) -> str:
        if not v:
            return "*"
        for part in v.split(','):
            if not re.match(r"([A-Za-z0-9*?-]{1,2})$", part):
                 raise ValueError(f"Invalid location code: {part}")
        return v

    @field_validator('channel')
    @classmethod
    def validate_channel(cls, v: Optional[str]) -> str:
        if not v:
            return "*"
        for part in v.split(','):
            if not re.match(r"([A-Za-z0-9*?]{1,3})$", part):
                 raise ValueError(f"Invalid channel code: {part}")
        return v

    @field_validator('quality')
    @classmethod
    def validate_quality(cls, v: str) -> str:
        # Pydantic regex support is built-in but manual logic was: [DMQR*?]{1}$
        # Also supports comma lists in original code?
        # Original: quality = params["quality"].split(",") ... check each
        # We'll allow comma separated string to be validated piece by piece
        parts = v.split(',')
        for part in parts:
            if not re.match(r"[DMQR*?]{1}$", part):
                raise ValueError(f"Invalid quality code: {part}")
        return v

    @field_validator('starttime', 'endtime')
    @classmethod
    def validate_datetime(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # If it's already a datetime object (from check_base_parameters), it's valid.
        if isinstance(v, datetime):
            return v
        if v == "currentutcday":
            return v
        # Try to parse to verify format, then return original string (or datetime obj if we prefer)
        # Original code kept it as string/datetime hybrid.
        for df in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                datetime.strptime(v.replace("Z", ""), df)
                return v
            except ValueError:
                pass
        raise ValueError(f"Invalid datetime format: {v}")

    @field_validator('mergegaps')
    @classmethod
    def validate_mergegaps(cls, v: Optional[float]) -> Optional[float]:
        # Original: is_valid_float(dimension, mini=sys.float_info.epsilon, maxi=sys.float_info.max)
        if v is not None:
             if v < sys.float_info.epsilon:
                 raise ValueError("Internal Server Error") # As per tests/code behavior for negative/zero? check utils
        return v

    @field_validator('includerestricted', mode='before')
    @classmethod
    def validate_bool(cls, v: str | bool) -> bool:
        if isinstance(v, bool):
            return v
        if v.lower() in STRING_TRUE:
            return True
        if v.lower() in STRING_FALSE:
            return False
        raise ValueError("Invalid boolean")

    @field_validator('format')
    @classmethod
    def validate_format(cls, v: str) -> str:
        if v.lower() not in OUTPUT:
            raise ValueError("Invalid output format")
        return v.lower()

    @field_validator('nodata')
    @classmethod
    def validate_nodata(cls, v: str) -> str:
        if v not in NODATA_CODE:
            raise ValueError("Invalid nodata code")
        return v

    @field_validator('orderby')
    @classmethod
    def validate_orderby(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ORDERBY:
            raise ValueError("Invalid orderby")
        return v

    @field_validator('show')
    @classmethod
    def validate_show(cls, v: str) -> str:
        if not v:
            return ""
        if v.lower() not in SHOW:
             raise ValueError("Invalid show parameter")
        return v

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Limit must be positive")
        return v
