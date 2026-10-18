namespace Samples.CSharpModern;

// Depend on TimeProvider, not DateTime.UtcNow, so tests can control time
public sealed class DueDateChecker(TimeProvider timeProvider)
{
    public bool IsOverdue(DateTimeOffset dueAt) => timeProvider.GetUtcNow() > dueAt;
}
