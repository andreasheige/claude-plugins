---
name: dotnet-containers
description: Containerizing .NET 10 apps: SDK container publish without a Dockerfile, chiseled and -extra images, non-root APP_UID, port 8080, Ubuntu default images, and a correct multi-stage Dockerfile when one is needed.
paths: ["**/*.cs", "**/*.csproj", "**/*.sln*", "**/*.razor", "**/*.cshtml"]
---

# Containers

If the repo has a Dockerfile or a pipeline that builds images, change that and keep its
approach. Infra and deployment changes are ask-first.

## Facts for .NET 8+ images (10 included)
- Images run as the non-root user `app`, UID **1654**, exposed as env var `APP_UID`.
- ASP.NET Core listens on **8080** (`ASPNETCORE_HTTP_PORTS=8080`), not 80.
- .NET 10: default tags (`10.0`) are **Ubuntu 24.04 "noble"**. No Debian images are
  shipped for .NET 10.
- Chiseled images (`10.0-noble-chiseled`) have no shell and no package manager, and they
  lack ICU and tzdata. They need `<InvariantGlobalization>true</InvariantGlobalization>`.
  If you need cultures or time zones, use `10.0-noble-chiseled-extra`.

## Preferred: SDK container publish (no Dockerfile)

```bash
dotnet publish --os linux --arch x64 -t:PublishContainer
```

This plain command pushes to the local Docker/Podman daemon and fails without one
(MSB4018 `CreateNewImage`). With no daemon, add `-p ContainerArchiveOutputPath=...` or
`-p ContainerRegistry=...`.

Useful properties (csproj or `-p:`):

```xml
<PropertyGroup>
  <ContainerRepository>samples-api</ContainerRepository>
  <ContainerFamily>noble-chiseled-extra</ContainerFamily>
  <ContainerImageTags>1.2.3;latest</ContainerImageTags>
</PropertyGroup>
```

- `ContainerFamily` is appended to the inferred tag (`aspnet:10.0-noble-chiseled-extra`).
  `ContainerBaseImage` sets the whole image instead and makes `ContainerFamily` ignored.
- `-p ContainerArchiveOutputPath=./images/app.tar.gz` writes a tarball without a container daemon (CI scanning).
- `-p ContainerRegistry=myregistry.azurecr.io` pushes straight to a registry (auth via `docker login`).
- The default user is already non-root. Never set `ContainerUser` to `root` without asking.
- No `RUN` steps are possible. If you need OS packages, build a custom base image or use a Dockerfile.

## When a Dockerfile is needed
Multi-stage. Restore from copied project files first so the restore layer is cached.
Copy each project file to **its own folder**: `COPY */*.csproj ./` flattens every project
into one directory and breaks project references. Copy `Directory.Build.props`,
`Directory.Packages.props` and `nuget.config` too if the repo has them, or restore fails.

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
# Only the files this repo has: Directory.Build.props, Directory.Packages.props, nuget.config
COPY Directory.Packages.props ./
COPY src/Api/Api.csproj src/Api/
COPY src/Core/Core.csproj src/Core/
RUN dotnet restore src/Api/Api.csproj
COPY . .
RUN dotnet publish src/Api/Api.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled
WORKDIR /app
COPY --from=build /app/publish .
USER $APP_UID
EXPOSE 8080
ENTRYPOINT ["dotnet", "Api.dll"]
```

- Add a `.dockerignore` with at least `**/bin/` and `**/obj/`. Without it, host `obj/`
  folders overwrite the restored ones from the earlier layer.
- `USER $APP_UID` matters on the non-chiseled images (they default to root); on chiseled
  images it just states the default.
- Pin base images by digest (`@sha256:...`) for reproducible, tamper-evident builds.

## Sources
Last verified: 2026-10-18. `PublishContainer` with `ContainerFamily=noble-chiseled-extra`
was run on `verify/Samples` to a tarball: base `aspnet:10.0-noble-chiseled-extra`, user 1654,
port 8080. The Dockerfile is a template and was not built (no container daemon on the
verifying machine).
- https://learn.microsoft.com/en-us/dotnet/core/containers/sdk-publish
- https://learn.microsoft.com/en-us/dotnet/core/containers/publish-configuration
- https://learn.microsoft.com/en-us/dotnet/core/docker/container-images
- https://learn.microsoft.com/en-us/dotnet/core/compatibility/containers/10.0/default-images-use-ubuntu
- https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/docker/building-net-docker-images
