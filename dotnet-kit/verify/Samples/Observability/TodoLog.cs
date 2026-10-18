namespace Samples.Observability;

internal static partial class TodoLog
{
    [LoggerMessage(Level = LogLevel.Information, Message = "Created todo {TodoId} with priority {Priority}")]
    public static partial void TodoCreated(this ILogger logger, int todoId, int priority);

    [LoggerMessage(Level = LogLevel.Error, Message = "Unhandled exception for {Method} {Path}")]
    public static partial void UnhandledException(this ILogger logger, Exception exception, string method, string path);
}
