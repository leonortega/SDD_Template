# db-bootstrap engine-client image (ADR-0003).
# Ships the database engine client (psql for the Postgres lab placeholder) —
# NOT an app runtime. The AI scaffold rewrites this image + src/bootstrap.sh
# for the engine selected in project-profile.local.json -> stack.database.
FROM postgres:16-alpine
COPY src/bootstrap.sh /bootstrap.sh
RUN chmod +x /bootstrap.sh
ENTRYPOINT ["/bootstrap.sh"]
