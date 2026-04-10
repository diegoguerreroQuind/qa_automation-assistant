Feature: Probar enviar notificacion Push

  Scenario: Notificacion push sin subAccountId vacio o no enviado
    Given que tengo los datos base para la peticion de enviar notificacion Push
    And ajusto la peticion de enviar notificacion Push para el caso sin subAccountId vacio o no enviado
    When envio la peticion hacia enviar notificacion Push
    Then el codigo de respuesta de enviar notificacion Push debe ser 400

  Scenario: Notificacion push con subAccountId no numerico caracteres alfabeticos
    Given que tengo los datos base para la peticion de enviar notificacion Push
    And ajusto la peticion de enviar notificacion Push para el caso con subAccountId no numerico caracteres alfabeticos
    When envio la peticion hacia enviar notificacion Push
    Then el codigo de respuesta de enviar notificacion Push debe ser 400