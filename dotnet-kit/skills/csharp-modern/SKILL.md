---
name: csharp-modern
description: Which C# 12, 13 and 14 features exist, which version each belongs to, and how to use them correctly. Use when writing new C#, choosing an idiom, or when unsure whether a feature is allowed by the project's LangVersion.
paths: ["**/*.cs", "**/*.csproj", "**/*.sln*", "**/*.razor", "**/*.cshtml"]
---

# Modern C# (12 to 14)

The repo's `LangVersion` (or its target framework's default) decides what you may use:
net8.0 = C# 12, net9.0 = C# 13, net10.0 = C# 14. Do not rewrite working code just to
use newer syntax; use new features in new code, matching the style around it.

## C# 14 (.NET 10)
| Feature | Note |
|---|---|
| Extension members (`extension(T receiver) { ... }` blocks) | Adds extension properties and static extension members. Classic `this` extension methods still work; do not convert them for style. |
| `field` keyword in property accessors | Was a preview in C# 13; stable only in 14. A member named `field` now needs `@field` or `this.field`. |
| Null-conditional assignment `a?.B = x`, `a?.B += x` | Right side is evaluated only when `a` is not null. `++`/`--` are not allowed. |
| `nameof` with unbound generics: `nameof(List<>)` | Returns `"List"`. |
| Implicit `Span<T>`/`ReadOnlySpan<T>` conversions | Arrays now bind to span-based extension methods. |
| Modifiers on simple lambda parameters | `(text, out result) => ...` without types. `params` still needs types. |
| Partial instance constructors and partial events | One defining and one implementing declaration each. |
| User-defined compound assignment (`operator +=`) and `++`/`--` | Instance `void` operators that mutate in place. |

Extension block, with instance and static members in one block:

```csharp
public static class StringExtensions
{
    extension(string value)
    {
        // Instance members: "text".IsBlank, "text".Truncate(3)
        public bool IsBlank => string.IsNullOrWhiteSpace(value);

        public string Truncate(int maxLength) =>
            value.Length <= maxLength ? value : value[..maxLength];

        // Static member on the extended type: string.JoinNonBlank(", ", parts)
        public static string JoinNonBlank(string separator, params IEnumerable<string?> parts) =>
            string.Join(separator, parts.Where(p => !string.IsNullOrWhiteSpace(p)));
    }
}
```

Two separate `extension(string ...)` blocks in one class can trip analyzer CA1708
(seen with `AnalysisLevel` `latest-recommended`). One block with both kinds of member avoids it.

`field`, null-conditional assignment, `nameof`, lambda modifiers, span conversion and
compound assignment:

```csharp
public sealed class Customer
{
    public required string Name
    {
        get;
        set => field = string.IsNullOrWhiteSpace(value)
            ? throw new ArgumentException("Name is required.", nameof(value))
            : value.Trim();
    }

    public Address? Address { get; set; }
}
```

```csharp
public sealed class Accumulator
{
    public decimal Total { get; private set; }

    // C# 14: instance compound assignment operator, mutates in place
    public void operator +=(decimal amount) => Total += amount;
}
```

```csharp
// Null-conditional assignment: right side runs only when customer is not null
customer?.Address = new Address { City = "Oslo" };

// nameof on an unbound generic type
var typeName = nameof(List<>); // "List"

// Modifiers on simple lambda parameters, no types needed
TryParser<int> parse = (text, out result) => int.TryParse(text, out result);
_ = parse("42", out var parsed);

// Arrays convert implicitly to ReadOnlySpan<T>, also as extension receiver
int[] numbers = [3, -1, 4];
var positives = numbers.CountPositive();
```

**Span overload trap (.NET 10 breaking change):** because arrays now convert to spans,
`array.Contains(x)` inside an `Expression<...>` can bind to `MemoryExtensions.Contains`.
That throws when the expression is compiled with interpretation. Fix it with
`((IEnumerable<int>)array).Contains(x)` or `Enumerable.Contains(array, x)`.

## C# 13 (.NET 9)
- `params` collections: `params ReadOnlySpan<T>`, `params IEnumerable<T>`, `params List<T>`.
- `System.Threading.Lock` type; `lock (_gate)` on a `Lock` uses its fast scope API.
- `\e` escape character.
- Implicit index `^` in object initializers.
- `ref` and `ref struct` locals in async methods and iterators (not live across `await`/`yield`);
  `unsafe` contexts in iterators (the `yield` statements themselves stay safe).
- `ref struct` types can implement interfaces; the `allows ref struct` generic anti-constraint.
- Partial properties and indexers.
- `[OverloadResolutionPriority]` for library authors.
- Better natural type for method groups.

Not C# 13: `field` (preview only in 13, stable in 14) and extension members (14).

## C# 12 (.NET 8)
- Primary constructors on classes and structs. The parameters are captured, mutable
  and not fields: do not reassign them, and copy to a `readonly` field if you need that guarantee.
- Collection expressions `[1, 2, ..other]`.
- Default values for lambda parameters; `ref readonly` parameters; `using` alias for any type.
- Inline arrays (`[InlineArray(n)]`), `[Experimental]`. Interceptors were a preview.

## Sources
Last verified: 2026-10-18. Every sample above compiles in `verify/` (net10.0, C# 14).
- https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-14
- https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-13
- https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-12
- https://learn.microsoft.com/en-us/dotnet/core/compatibility/core-libraries/10.0/csharp-overload-resolution
- https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/configure-language-version
