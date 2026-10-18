using Microsoft.Extensions.Time.Testing;
using Samples.CSharpModern;

namespace Samples.Tests;

public sealed class TimeAndLanguageTests
{
    [Fact]
    public void FakeTimeProvider_controls_now()
    {
        var time = new FakeTimeProvider(new DateTimeOffset(2026, 1, 1, 12, 0, 0, TimeSpan.Zero));
        var checker = new DueDateChecker(time);
        var dueAt = time.GetUtcNow().AddHours(1);

        Assert.False(checker.IsOverdue(dueAt));
        time.Advance(TimeSpan.FromHours(2));
        Assert.True(checker.IsOverdue(dueAt));
    }

    [Fact]
    public void CSharp14_features_behave_as_documented()
    {
        Assert.Equal("List 42 2 10", FeatureDemo.Run(null));

        var customer = new Customer { Name = "  Ada  " };
        FeatureDemo.Run(customer);
        Assert.Equal("Ada", customer.Name);
        Assert.Equal("Oslo", customer.Address?.City);

        Assert.Equal("a, b", ExtensionUsage.Run()); // "   ".IsBlank is true, so the null is dropped
        Assert.Throws<ArgumentException>(() => new Customer { Name = " " });
    }
}
