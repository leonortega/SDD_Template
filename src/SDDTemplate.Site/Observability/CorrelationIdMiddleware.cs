using Serilog.Context;

namespace SDDTemplate.Site.Observability
{
    internal sealed class CorrelationIdMiddleware(RequestDelegate next)
    {
        public const string CorrelationHeaderName = "X-Correlation-ID";
        internal const string CorrelationItemKey = "CorrelationId";

        public async Task InvokeAsync(HttpContext context)
        {
            string correlationId = ResolveCorrelationId(context);
            context.Items[CorrelationItemKey] = correlationId;
            context.Response.Headers[CorrelationHeaderName] = correlationId;

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

    internal static class CorrelationIdMiddlewareExtensions
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
