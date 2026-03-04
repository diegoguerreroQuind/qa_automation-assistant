describe('API Test: enviar notificacion Whatsapp', () => {
  it('should successfully send a Whatsapp notification', () => {
    cy.request({
      method: 'POST',
      url: `${Cypress.env('url-host-marketing-notification')}/marketing-notifications/api/v1/notifications`,
      headers: {},
      body: {
        "contextSource": "ZER",
        "subAccountId": "11834639",
        "shippingMethods": [
          {
            "channel": "WHATSAPP",
            "phoneNumber": "573017831189",
            "templateName": "interoperability_adhoc_parkingmeter_download_the_app_wp",
            "templateParams": [
              "HDS910",
              "Pablo CAR",
              "1400"
            ]
          }
        ]
      }
    }).then((response) => {
      expect(response.status).to.be.oneOf([200, 201]);
    });
  });
});