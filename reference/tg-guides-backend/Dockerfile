# Используем базовый образ с Maven и JDK
FROM maven:3.8.8-eclipse-temurin-17 AS build

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . .

# Запускаем сборку проекта с помощью Maven
RUN mvn clean package -DskipTests

# Используем базовый образ с JDK для запуска приложения
FROM eclipse-temurin:17-jdk

# Устанавливаем рабочую директорию для приложения
WORKDIR /app

# Копируем собранный JAR-файл из предыдущего шага
COPY --from=build /app/target/guides-0.0.1-SNAPSHOT.jar backend.jar

# Указываем команду для запуска приложения
CMD ["java", "-jar", "backend.jar"]
