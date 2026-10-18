namespace Samples.CSharpModern;

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

public static class SpanExtensions
{
    public static int CountPositive(this ReadOnlySpan<int> values)
    {
        var count = 0;
        foreach (var value in values)
        {
            if (value > 0)
            {
                count++;
            }
        }

        return count;
    }
}
