import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("que tengo los datos para 'enviar notificacion Push'", () => {
    const requestBody = {
        "contextSource": "ZER",
        "flyKey": "ADE748",
        "subAccountId": "40378",
        "shippingMethods": [
            {
                "channel": "PUSH",  
                "title": "Notificación PUSH",
                "body": "Este es un mensaje de prueba para Push, #$%&/-+@_",
                "image": "https://media.istockphoto.com/id/1674601384/es/foto/mujer-de-negocios-madura-que-busca-un-holograma-en-la-oficina.jpg?s=1024x1024&w=is&k=20&c=9P6v1czgmDZAtyA7voi4GzmwoKr24POqL2EIzu06RZ4=",
                "data": {
                    "to": "parkingmeterCompleteTransaction",
                    "amount": 1000,
                    "approvePath": "https://test.services.flypass.co/parkingmeter/api/v1/transactions/approve/true",
                    "disapprovePath": "https://test.services.flypass.co/parkingmeter/api/v1/transactions/approve/false",
                    "transactionId": "test_COS039_58",
                    "stationId": "15",
                    "completeTransaction": false
                }
            }
        ]
    };
    const requestHeaders = {};

    cy.wrap(requestBody).as('requestBody');
    cy.wrap(requestHeaders).as('requestHeaders');
});

When("envío la petición hacia 'enviar notificacion Push'", () => {
    cy.get('@requestBody').then((body) => {
        cy.get('@requestHeaders').then((headers) => {
            cy.request({
                method: 'POST',
                url: `${Cypress.env('url-host-marketing-notification')}/marketing-notifications/api/v1/notifications`,
                headers: headers,
                body: body,
                failOnStatusCode: false
            }).as('apiResponse');
        });
    });
});

Then("el código de respuesta para 'enviar notificacion Push' debe ser exitoso", () => {
    cy.get('@apiResponse').then((response: any) => {
        expect(response.status).to.be.oneOf([200, 201, 202, 204]);
    });
});