import subprocess, sys
sys.path.insert(0, r"C:\Users\henriqueal\Desktop\ISO Analyzer")
from audit.utils.tools import build_env_with_java

env = build_env_with_java()
env["SPRING_DATASOURCE_URL"] = "jdbc:h2:mem:auditdb;DB_CLOSE_DELAY=-1;MODE=MySQL"
env["SPRING_DATASOURCE_DRIVER_CLASS_NAME"] = "org.h2.Driver"
env["SPRING_DATASOURCE_USERNAME"] = "sa"
env["SPRING_DATASOURCE_PASSWORD"] = ""
env["SPRING_JPA_HIBERNATE_DDL_AUTO"] = "create-drop"
env["SERVER_PORT"] = "8080"

r = subprocess.run(
    [
        r"C:\Users\henriqueal\Desktop\ISO Analyzer\tools\maven\apache-maven-3.9.9\bin\mvn.cmd",
        "spring-boot:run",
        "-Dlombok.version=1.18.36",
        "-Dspring-boot.run.additionalClasspathElements=C:/Users/henriqueal/.m2/repository/com/h2database/h2/2.2.224/h2-2.2.224.jar",
    ],
    capture_output=True, text=True, timeout=90, env=env, errors="replace",
    cwd=r"C:\Users\henriqueal\Desktop\ISO Analyzer\audit-output\.tmp_clones\spring-boot-crud-example",
)
print("Exit code:", r.returncode)
output = (r.stdout or "") + (r.stderr or "")
print(output[-3500:])

