import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

let requestConfig: any = {
    method: "POST",
    url: `${Cypress.env("url-host-marketing-notification")}/marketing-notifications/api/v1/notifications`,
    headers: {},
    body: {},
    failOnStatusCode: false
};

let responseObj: any;

Given("que tengo los datos base para la peticion de enviar notificacion Push", () => {
    requestConfig.body = {
        contextSource: "ZER",
        flyKey: "ADE748",
        subAccountId: "40378",
        shippingMethods: [
            {
                channel: "PUSH",
                title: "Notificación PUSH",
                body: "Este es un mensaje de prueba para Push, #$%&/-+@_",
                image: "https://media.istockphoto.com/id/1674601384/es/foto/mujer-de-negocios-madura-que-busca-un-holograma-en-la-oficina.jpg?s=1024x1024&w=is&k=20&c=9P6v1czgmDZAtyA7voi4GzmwoKr24POqL2EIzu06RZ4=",
                data: {
                    to: "parkingmeterCompleteTransaction",
                    amount: 1000,
                    approvePath: "https://test.services.flypass.co/parkingmeter/api/v1/transactions/approve/true",
                    disapprovePath: "https://test.services.flypass.co/parkingmeter/api/v1/transactions/approve/false",
                    transactionId: "test_COS039_58",
                    stationId: "15",
                    completeTransaction: false
                }
            }
        ]
    };
});

Given("ajusto la peticion de enviar notificacion Push para el caso sin subAccountId", () => {
    delete requestConfig.body.subAccountId;
});

Given("ajusto la peticion de enviar notificacion Push para el caso con subAccountId no numerico", () => {
    requestConfig.body.subAccountId = "ABCXYZ";
});

When("envio la peticion hacia enviar notificacion Push", () => {
    cy.request(requestConfig).then((response) => {
        responseObj = response;
    });
});

Then("el codigo de respuesta de enviar notificacion Push debe ser 400", () => {
    expect(responseObj.status).to.eq(400);
});