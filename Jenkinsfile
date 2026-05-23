pipeline {
    agent {
        kubernetes {
            namespace 'jenkins-agents'
            inheritFrom 'jenkins-agent'
            yaml '''
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-agent
  imagePullSecrets:
  - name: harbor-credentials
  containers:
  - name: jenkins-agent
    image: harbor.rmwhs.space/devops/jenkins-agent:latest
    imagePullPolicy: Always
    command:
    - sleep
    args:
    - infinity
    tty: true
    env:
    - name: DOCKER_HOST
      value: tcp://localhost:2375
  - name: dind
    image: docker:24-dind
    securityContext:
      privileged: true
    env:
    - name: DOCKER_TLS_CERTDIR
      value: ""
'''
            defaultContainer 'jenkins-agent'
        }
    }

    parameters {
        booleanParam(
            name: 'RESET_DB',
            defaultValue: false,
            description: 'Drop and recreate the database schema. WARNING: destroys all data.'
        )
    }

    environment {
        HARBOR_REGISTRY  = 'harbor.rmwhs.space'
        HARBOR_PROJECT   = 'apps'
        IMAGE_NAME       = 'ai-python-demo'
        IMAGE_TAG        = "${BUILD_NUMBER}"
        FULL_IMAGE       = "${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
        LATEST_IMAGE     = "${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:latest"
        SONAR_PROJECT    = 'ai-python-demo'
        K8S_NAMESPACE    = 'ai-python-demo'
    }

    stages {

        stage('Pre-flight Checks') {
            steps {
                checkout scm
                sh '''
                    test -f k8s/db-secret.yaml || \
                      (echo "ERROR: k8s/db-secret.yaml template is missing from the repo" && exit 1)
                    echo "k8s/db-secret.yaml present — OK"
                    git log --oneline -5
                '''
            }
        }

        stage('Prepare K8s Namespace & Registry Secret') {
            steps {
                sh 'kubectl create namespace ${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -'
                withCredentials([usernamePassword(credentialsId: 'harbor-credentials', usernameVariable: 'USER', passwordVariable: 'PASS')]) {
                    sh '''
                        kubectl create secret docker-registry harbor-credentials \
                          --namespace ${K8S_NAMESPACE} \
                          --docker-server=${HARBOR_REGISTRY} \
                          --docker-username=${USER} \
                          --docker-password=${PASS} \
                          --dry-run=client -o yaml | kubectl apply -f -
                    '''
                }
            }
        }

        stage('Apply App Secret') {
            steps {
                withVault(configuration: [vaultUrl: 'https://vault.rmwhs.space',
                                          vaultCredentialId: 'vault-auth-token'],
                          vaultSecrets: [[path: 'kv/ai-python-demo',
                                         secretValues: [
                                             [envVar: 'DB_USER', vaultKey: 'db_user'],
                                             [envVar: 'DB_PASS', vaultKey: 'db_pass'],
                                             [envVar: 'DB_NAME', vaultKey: 'db_name'],
                                             [envVar: 'APP_KEY',  vaultKey: 'app_key']
                                         ]]]) {
                    sh """
                        envsubst '\$DB_USER \$DB_PASS \$DB_NAME \$APP_KEY' \
                          < k8s/db-secret.yaml | kubectl apply -f -
                    """
                }
            }
        }

        stage('SonarQube Scan') {
            when { branch 'main' }
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh '''
                        sonar-scanner \
                          -Dsonar.projectKey=${SONAR_PROJECT} \
                          -Dsonar.projectName="AI Python Demo" \
                          -Dsonar.sources=. \
                          -Dsonar.exclusions=**/migrations/**,**/__pycache__/**,**/static/**,**/templates/**,**/tests/**
                    '''
                }
            }
        }

        stage('Quality Gate') {
            when { branch 'main' }
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build \
                      -t ${FULL_IMAGE} \
                      -t ${LATEST_IMAGE} \
                      .
                '''
            }
        }

        stage('Trivy Image Scan') {
            steps {
                sh '''
                    trivy image \
                      --exit-code 0 \
                      --severity CRITICAL \
                      --no-progress \
                      --format table \
                      ${FULL_IMAGE}
                '''
            }
        }

        stage('Push to Harbor') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'harbor-credentials',
                    usernameVariable: 'HARBOR_USER',
                    passwordVariable: 'HARBOR_PASS'
                )]) {
                    sh '''
                        echo "${HARBOR_PASS}" | docker login ${HARBOR_REGISTRY} -u ${HARBOR_USER} --password-stdin
                        docker push ${FULL_IMAGE}
                        docker push ${LATEST_IMAGE}
                    '''
                }
            }
        }

        stage('DB Setup') {
            steps {
                withVault(configuration: [vaultUrl: 'https://vault.rmwhs.space',
                                          vaultCredentialId: 'vault-auth-token'],
                          vaultSecrets: [[path: 'kv/ai-python-demo',
                                         secretValues: [
                                             [envVar: 'DB_USER', vaultKey: 'db_user'],
                                             [envVar: 'DB_PASS', vaultKey: 'db_pass'],
                                             [envVar: 'DB_NAME', vaultKey: 'db_name'],
                                             [envVar: 'APP_KEY',  vaultKey: 'app_key']
                                         ]]]) {
                    script {
                        // Ensure postgres is deployed and ready
                        sh '''
                            kubectl apply -f k8s/postgres-init-configmap.yaml -n ${K8S_NAMESPACE}
                            kubectl apply -f k8s/postgres.yaml -n ${K8S_NAMESPACE}
                            kubectl rollout status deployment/postgres -n ${K8S_NAMESPACE} --timeout=120s
                        '''

                        def resetDb = params.RESET_DB ? 'true' : 'false'

                        // Render the DB setup Job with Vault credentials
                        def dbSetupSql = params.RESET_DB
                            ? "DROP SCHEMA IF EXISTS blog CASCADE; CREATE SCHEMA blog;"
                            : "CREATE DATABASE IF NOT EXISTS \\\"${env.DB_NAME}\\\"; CREATE SCHEMA IF NOT EXISTS blog;"

                        writeFile file: '/tmp/db-setup-job.yaml', text: """
apiVersion: batch/v1
kind: Job
metadata:
  name: db-setup-${env.BUILD_NUMBER}
  namespace: ${env.K8S_NAMESPACE}
spec:
  ttlSecondsAfterFinished: 600
  backoffLimit: 2
  template:
    spec:
      restartPolicy: Never
      imagePullSecrets:
      - name: harbor-credentials
      containers:
      - name: db-setup
        image: postgres:15-alpine
        command:
        - sh
        - -c
        - |
          set -e
          echo "Waiting for postgres..."
          until pg_isready -h postgres -U ${env.DB_USER}; do sleep 2; done
          echo "Postgres ready."
          ${params.RESET_DB
              ? "psql -h postgres -U \\\"${env.DB_USER}\\\" -d postgres -c \\\"DROP SCHEMA IF EXISTS blog CASCADE;\\\"; psql -h postgres -U \\\"${env.DB_USER}\\\" -d \\\"${env.DB_NAME}\\\" -c \\\"CREATE SCHEMA IF NOT EXISTS blog;\\\""
              : "psql -h postgres -U \\\"${env.DB_USER}\\\" -d postgres -c \\\"SELECT 1 FROM pg_database WHERE datname='${env.DB_NAME}'\\\" | grep -q 1 || psql -h postgres -U \\\"${env.DB_USER}\\\" -d postgres -c \\\"CREATE DATABASE \\\\\\\"${env.DB_NAME}\\\\\\\"\\\"; psql -h postgres -U \\\"${env.DB_USER}\\\" -d \\\"${env.DB_NAME}\\\" -c \\\"CREATE SCHEMA IF NOT EXISTS blog;\\\""
          }
          echo "DB setup complete."
        env:
        - name: PGPASSWORD
          value: "${env.DB_PASS}"
"""
                        sh '''
                            kubectl delete job -n ${K8S_NAMESPACE} \
                              --selector=app=db-setup --ignore-not-found=true
                            kubectl apply -f /tmp/db-setup-job.yaml
                            kubectl wait job/db-setup-${BUILD_NUMBER} \
                              -n ${K8S_NAMESPACE} \
                              --for=condition=complete \
                              --timeout=120s
                        '''
                    }
                }
            }
        }

        stage('DB Migration') {
            steps {
                withVault(configuration: [vaultUrl: 'https://vault.rmwhs.space',
                                          vaultCredentialId: 'vault-auth-token'],
                          vaultSecrets: [[path: 'kv/ai-python-demo',
                                         secretValues: [
                                             [envVar: 'DB_USER', vaultKey: 'db_user'],
                                             [envVar: 'DB_PASS', vaultKey: 'db_pass'],
                                             [envVar: 'DB_NAME', vaultKey: 'db_name'],
                                             [envVar: 'APP_KEY',  vaultKey: 'app_key']
                                         ]]]) {
                    script {
                        // Apply PVC for migration logs (idempotent)
                        sh 'kubectl apply -f k8s/migration-pvc.yaml -n ${K8S_NAMESPACE}'

                        writeFile file: '/tmp/db-migrate-job.yaml', text: """
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate-${env.BUILD_NUMBER}
  namespace: ${env.K8S_NAMESPACE}
spec:
  ttlSecondsAfterFinished: 600
  backoffLimit: 2
  template:
    spec:
      restartPolicy: Never
      imagePullSecrets:
      - name: harbor-credentials
      containers:
      - name: db-migrate
        image: ${env.FULL_IMAGE}
        imagePullPolicy: Always
        command:
        - sh
        - -c
        - |
          set -o pipefail
          flask db upgrade 2>&1 | tee /migration-logs/migration-${env.BUILD_NUMBER}.log
          echo "Migration exit code: \$?"
        env:
        - name: DATABASE_URL
          value: "postgresql://${env.DB_USER}:${env.DB_PASS}@postgres:5432/${env.DB_NAME}"
        - name: SECRET_KEY
          value: "${env.APP_KEY}"
        - name: FLASK_APP
          value: app.py
        - name: FLASK_ENV
          value: production
        volumeMounts:
        - name: migration-logs
          mountPath: /migration-logs
      volumes:
      - name: migration-logs
        persistentVolumeClaim:
          claimName: migration-logs-pvc
"""
                        sh '''
                            kubectl delete job -n ${K8S_NAMESPACE} \
                              --selector=app=db-migrate --ignore-not-found=true
                            kubectl apply -f /tmp/db-migrate-job.yaml
                            kubectl wait job/db-migrate-${BUILD_NUMBER} \
                              -n ${K8S_NAMESPACE} \
                              --for=condition=complete \
                              --timeout=300s
                        '''
                    }
                }
            }
        }

        stage('Update Image Tag') {
            steps {
                sh '''
                    sed -i "s|harbor.rmwhs.space/apps/ai-python-demo:.*|harbor.rmwhs.space/apps/ai-python-demo:${IMAGE_TAG}|g" \
                      k8s/deployment-with-fluent-bit.yaml
                '''
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    kubectl apply -f k8s/configmap.yaml
                    kubectl apply -f k8s/fluent-bit-configmap.yaml
                    kubectl apply -f k8s/deployment-with-fluent-bit.yaml
                    kubectl apply -f k8s/service.yaml
                    kubectl apply -f k8s/ingress.yaml
                    kubectl apply -f k8s/servicemonitor.yaml
                    kubectl rollout status deployment/ai-python-demo -n ${K8S_NAMESPACE} --timeout=300s
                '''
            }
        }
    }

    post {
        success {
            echo "Deployed ${FULL_IMAGE} to ${K8S_NAMESPACE} successfully."
        }
        failure {
            echo 'Pipeline failed.'
        }
    }
}
