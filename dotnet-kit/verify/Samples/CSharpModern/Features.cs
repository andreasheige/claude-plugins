namespace Samples.CSharpModern;

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

public sealed class Address
{
    public string? City { get; set; }
}

public sealed class Accumulator
{
    public decimal Total { get; private set; }

    // C# 14: instance compound assignment operator, mutates in place
    public void operator +=(decimal amount) => Total += amount;
}

public delegate bool TryParser<T>(string text, out T result);

public static class FeatureDemo
{
    public static string Run(Customer? customer)
    {
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

        var total = new Accumulator();
        total += 10m;

        return $"{typeName} {parsed} {positives} {total.Total}";
    }
}

public partial class Widget
{
    // Defining declarations (often written by a source generator's consumer)
    public partial Widget(string name);

    public partial event EventHandler? Renamed;
}

public partial class Widget
{
    private EventHandler? _renamed;

    // Implementing declarations
    public partial Widget(string name)
    {
        Name = name;
    }

    public partial event EventHandler? Renamed
    {
        add => _renamed += value;
        remove => _renamed -= value;
    }

    public string Name { get; private set; }

    public void Rename(string name)
    {
        Name = name;
        _renamed?.Invoke(this, EventArgs.Empty);
    }
}

public static class ExtensionUsage
{
    public static string Run() =>
        string.JoinNonBlank(", ", "a", " ", "b".Truncate(1), "   ".IsBlank ? null : "c");
}
