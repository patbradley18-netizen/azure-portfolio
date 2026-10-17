// Merge app settings into a Function app's existing bag. A sites/config 'appsettings' resource replaces the whole set, so the
// PARENT reads the live set with list() (the parent does not deploy that config, so no circular dependency) and passes it in;
// this module writes the union. Nothing secret crosses the boundary as a literal: `existing` is whatever the platform already holds.
param siteName string
@secure()
param existing object
param settings object

resource site 'Microsoft.Web/sites@2024-04-01' existing = { name: siteName }

resource merged 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: site
  name: 'appsettings'
  properties: union(existing, settings)
}
