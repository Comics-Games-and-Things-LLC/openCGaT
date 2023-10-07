#!/usr/bin/env groovy

node {
    checkout scm
    def djangoImage
    def nodeImage
    stage('Build') {
        echo 'Building...'
        nodeImage = docker.image('node:18')
        nodeImage.inside('-v /output/:/output/ -u root'){
            sh 'rm -r ./tailwind/static/* ./openCGaT/static/js/* ./static/* || true'
            sh 'rm -r /output/css/* /output/js/* || true'
            sh 'yarn install'
            sh 'yarn build'
            sh 'cp -r ./tailwind/static/css/ /output/css/'
            sh 'cp -r ./openCGaT/static/js/ /output/js/'
        }
        djangoImage = docker.build("registry.digitalocean.com/cgt/opencgat:${env.BUILD_ID}")
        djangoImage.inside('-v /output/:/output/ -u root'){
            sh 'mkdir -p openCGaT/static/js/'
            sh 'cp -r /output/css/ openCGaT/static/css/'
            sh 'cp -r /output/js/ openCGaT/static/js/'
        }
    }
    stage('Test') {
        echo 'Testing...'
        //test npm here
        withCredentials([file(credentialsId: 'jenkins.env', variable: 'env_file')]){
            djangoImage.inside('-u root --env-file $env_file'){
                sh 'cd /app/'
                sh './manage.py test --no-input'
            }
        }
    }
    stage('Deploy'){
        echo 'Deploying...'
        djangoImage.inside('-u root'){
            sh 'cd /app/'
            sh './manage.py collectstatic --no-input'
        }
        docker.withRegistry('https://registry.digitalocean.com/cgt/', 'dodockerauth'){
            djangoImage.push()
            djangoImage.push('latest')
        }
        // Run migrations on the database
        withCredentials([file(credentialsId: 'jenkins.env', variable: 'env_file')]){
            djangoImage.inside('-u root --env-file $env_file'){
                sh 'cd /app/'
                sh './manage.py migrate'
            }
        }
        //Pushing the latest container should auto-trigger a deploy.
        //sh "doctl apps create-deployment ${params.doappcluserid}"
    }
}
