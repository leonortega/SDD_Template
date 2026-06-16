using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.Hosting;
using Serilog;

namespace SDDTemplate.Common.Observability
{
    public static class WebApplicationLogging
    {
        public static IHostBuilder UseStandardSerilog(this IHostBuilder host)
        {
            return host.UseSerilog((context, services, loggerConfiguration) => loggerConfiguration
                .ReadFrom.Configuration(context.Configuration)
                .ReadFrom.Services(services)
                .Enrich.FromLogContext());
        }

        public static IApplicationBuilder UseCorrelationAwareRequestLogging(this IApplicationBuilder app)
        {
            return app.UseSerilogRequestLogging(options =>
            {
                options.EnrichDiagnosticContext = (diagnosticContext, httpContext) =>
                {
                    diagnosticContext.Set("CorrelationId", httpContext.GetCorrelationId());
                    diagnosticContext.Set("RequestPath", httpContext.Request.Path.Value ?? string.Empty);
                    diagnosticContext.Set("RequestMethod", httpContext.Request.Method);
                };
            });
        }
    }
}
