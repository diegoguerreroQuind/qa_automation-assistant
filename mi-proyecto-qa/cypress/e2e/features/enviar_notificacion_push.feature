Feature: Probar enviar notificacion Push

  Scenario: Notificacion push sin subAccountId
    Given que tengo los datos base para la peticion de enviar notificacion Push
    And ajusto la peticion de enviar notificacion Push para el caso sin subAccountId
    When envio la peticion hacia enviar notificacion Push
    Then el codigo de respuesta de enviar notificacion Push debe ser 400

  Scenario: Notificacion push con subAccountId no numerico
    Given que tengo los datos base para la peticion de enviar notificacion Push
    And ajusto la peticion de enviar notificacion Push para el caso con subAccountId no numerico
    When envio la peticion hacia enviar notificacion Push
    Then el codigo de respuesta de enviar notificacion Push debe ser 400