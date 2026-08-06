# Benchmark API

## Functions

`clean_01(x: int) -> int`

Increments integer.

`clean_02(text: str) -> str`

Strips whitespace.

`clean_03(items: list) -> int`

Returns length.

`clean_04(a: int, b: int) -> int`

Adds two numbers.

`clean_05(flag: bool = False) -> bool`

Returns flag.

`clean_06(data: dict) -> dict`

Identity on dict.

`clean_07(n: float) -> float`

Doubles float.

`clean_08(s: str) -> str`

Lowercases string.

`clean_09(values: list) -> list`

Sorts values.

`clean_10(key: str) -> str`

Uppercases key.

`type_01(data: str) -> dict`

Doc says dict.

`type_02(n: int) -> str`

Doc says str.

`type_03(x: float) -> int`

Doc says int.

`type_04(items: list) -> list`

Doc says list, code dict ann.

`type_05(s: str) -> bool`

Doc says bool.

`type_06(v: int) -> float`

Doc says float.

`type_07(m: dict) -> str`

Doc says str.

`type_08(a: int, b: int) -> int`

Doc says int, returns str.

`type_09(f: float) -> None`

Doc says None.

`type_10(b: bool) -> int`

Doc says int.

`param_01(a: int, b: int) -> int`

Doc has extra param.

`param_02(x: str) -> str`

Code has extra param.

`param_03(user_id: int) -> int`

Param name differs.

`param_04(message: str) -> str`

Param name differs.

`param_05(count: int) -> int`

Param type differs.

`param_06(rate: float) -> float`

Param type differs.

`param_07(payload: dict) -> dict`

Param type differs.

`param_08(verbose: bool = False) -> bool`

Default differs.

`param_09(limit: int = 10) -> int`

Default differs.

`param_10(mode: str = 'r') -> str`

Default differs.

`struct_01(q: str) -> list[dict]`

Doc list[dict], code dict.

`struct_02(id: int) -> dict`

Doc dict, code list.

`struct_03(n: int) -> list[dict]`

Doc list[dict], code list.

`struct_04(k: str) -> list[dict]`

Doc list[dict], code dict.

`struct_05(page: int) -> list[dict]`

Structure mismatch.

`struct_06(token: str) -> dict`

Structure mismatch.

`struct_07(rows: int) -> list[dict]`

Structure mismatch.

`struct_08(name: str) -> dict`

Structure mismatch.

`struct_09(size: int) -> list[dict]`

Structure mismatch.

`struct_10(code: str) -> dict`

Doc dict, code list annotation.
