# Backend del bot de Bitcoin: imagen en dos etapas.
# El servidor lee el puerto de la variable PORT (Railway la inyecta; sin ella usa 8080).

# ---------- Etapa 1: construcción ----------
FROM maven:3.9.9-eclipse-temurin-21 AS construccion
WORKDIR /build

# Primero solo el pom.xml: mientras no cambie, Docker reutiliza esta capa con las
# dependencias ya descargadas y no las vuelve a bajar en cada construcción.
COPY pom.xml .
RUN mvn -B -q dependency:go-offline

# Después el código, y se empaqueta el jar (las pruebas corren en el CI).
COPY src ./src
RUN mvn -B -DskipTests package && cp target/backend-*.jar target/app.jar

# ---------- Etapa 2: ejecución ----------
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Usuario sin privilegios. La carpeta ./data (DATA_DIR por defecto) le pertenece.
RUN addgroup -S backend && adduser -S -G backend -H -h /app backend \
    && mkdir -p /app/data && chown -R backend:backend /app

# Solo el jar de la etapa anterior; Maven y el código fuente no llegan a esta imagen.
COPY --from=construccion --chown=backend:backend /build/target/app.jar /app/backend.jar

USER backend

# Poca memoria: montículo de 256 MB y el recolector de basura más simple.
ENV JAVA_OPTS="-Xmx256m -XX:+UseSerialGC"

# "sh -c" para que se expanda $JAVA_OPTS; "exec" para que Java reciba las señales de apagado.
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/backend.jar"]
