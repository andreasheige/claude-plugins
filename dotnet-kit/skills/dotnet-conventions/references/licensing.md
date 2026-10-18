# Licensing traps in common .NET packages

Check before adding or upgrading a package. "Free" depends on the version. A major bump
in a Renovate/Dependabot PR can move a client project onto a commercial licence.
Commercial-licence decisions belong to the user/client, so ask; don't decide.

| Package | Last permissive version (licence) | From version | Licence after |
|---|---|---|---|
| MediatR | 12.5.0 (Apache-2.0, **not MIT**) | 13.0 (2025-07-02) | Dual RPL-1.5 / commercial (Lucky Penny Software); free community tier under revenue limits |
| AutoMapper | 14.x (MIT) | 15.x (first on NuGet: 15.0.1) | Dual RPL-1.5 / commercial (Lucky Penny Software) |
| FluentAssertions | 7.x (Apache-2.0) | 8.0 | Xceed licence; free for open-source and non-commercial use, paid for commercial use |
| MassTransit | 8.x (Apache-2.0) | 9.0 | Commercial |

Notes:
- Pinning the last permissive version is a valid choice, but it gets no new features and,
  eventually, no security fixes. Run `dotnet package list --vulnerable` on the pinned
  version. Record the decision.
- Permissive alternatives: plain DI handlers or Wolverine (MIT) instead of MediatR;
  hand-written mapping or Mapperly (Apache-2.0, source generator) instead of AutoMapper;
  xUnit `Assert` or Shouldly (BSD-3-Clause) instead of FluentAssertions.
- Check the licence that applies to the exact version: nuget.org →
  package → version → "License Info".

Last verified: 2026-10-18 against nuget.org licence pages and the vendors' announcements:
- https://www.jimmybogard.com/automapper-and-mediatr-commercial-editions-launch-today/
- https://www.nuget.org/packages/AutoMapper/15.0.1/License
- https://packages.nuget.org/packages/FluentAssertions/8.3.0/License
- https://www.nuget.org/packages/MassTransit
