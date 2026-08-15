# estar CLI tool 

## basic workflow 

Initialize and setup the system-wide environment for deploying **mondoo**:

```
    # it will help initialize some necessary setup in system-wide
    estar init
```

Export the configuration files template:

```
estar config -D --out-dir config
```

Launch Web API services

```
    estar launch -C config --filter <list of service name>
```

