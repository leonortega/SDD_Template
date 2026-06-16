using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Serilog.Context;

namespace SDDTemplate.Common.Observability
{
    public sealed class CorrelationIdMiddleware(RequestDelegate next, ILogger<CorrelationIdMiddleware> logger)
    {
        public const string CorrelationHeaderName = "X-Correlation-ID";
        public const string CorrelationItemKey = "CorrelationId";

        public async Task InvokeAsync(HttpContext context)
        {
            string correlationId = ResolveCorrelationId(context);
            context.Items[CorrelationItemKey] = correlationId;
            context.Response.Headers[CorrelationHeaderName] = correlationId;

            logger.LogDebug(
                "Correlation ID {CorrelationId} assigned for {Method} {Path}",
                correlationId,
                context.Request.Method,
                context.Request.Path);

            using (LogContext.PushProperty("CorrelationId", correlationId))
            {
                await next(context);
            }
        }

        private static string ResolveCorrelationId(HttpContext context)
        {
            if (context.Request.Headers.TryGetValue(CorrelationHeaderName, out Microsoft.Extensions.Primitives.StringValues values))
            {
                string? incoming = values.FirstOrDefault();
                if (!string.IsNullOrWhiteSpace(incoming))
                {
                    return incoming.Trim();
                }
            }

            return Guid.NewGuid().ToString("N");
        }
    }

    public static class CorrelationIdMiddlewareExtensions
    {
        public static IApplicationBuilder UseCorrelationId(this IApplicationBuilder app)
        {
            return app.UseMiddleware<CorrelationIdMiddleware>();
        }

        public static string GetCorrelationId(this HttpContext context)
        {
            return context.Items.TryGetValue(CorrelationIdMiddleware.CorrelationItemKey, out object? value) && value is string correlationId
                ? correlationId
                : context.Request.Headers.TryGetValue(CorrelationIdMiddleware.CorrelationHeaderName, out Microsoft.Extensions.Primitives.StringValues values)
                    ? values.FirstOrDefault() ?? string.Empty
                    : string.Empty;
        }
    }
}
